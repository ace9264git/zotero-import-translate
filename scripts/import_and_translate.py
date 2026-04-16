#!/usr/bin/env python3

import argparse
import html
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib import error, parse, request

from llm_translate import TranslationError, translate_text
from ocr_utils import OCRExtractionError, extract_text_from_pdf
from zotero_client import ZoteroClient, ZoteroError


DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
NOTE_CHAR_LIMIT = 90000


def log(message: str) -> None:
    print(message, file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a paper into Zotero, attach files, and create a full-text translation."
    )
    parser.add_argument("--doi", help="DOI for metadata lookup")
    parser.add_argument("--url", help="Article URL or DOI URL")
    parser.add_argument("--pdf", help="Path to a local PDF file")
    parser.add_argument("--pdf-url", help="Direct URL to a downloadable PDF file")
    parser.add_argument("--text-file", help="Plain text source used for translation instead of a PDF")
    parser.add_argument("--title", help="Manual title override")
    parser.add_argument(
        "--use-filename-as-fallback-title",
        action="store_true",
        help="Use the source filename as a fallback title when DOI metadata is unavailable",
    )
    parser.add_argument("--author", action="append", default=[], help="Repeatable author name")
    parser.add_argument("--year", help="Manual year or date")
    parser.add_argument("--journal", help="Manual journal or container title")
    parser.add_argument("--abstract", help="Manual abstract")
    parser.add_argument("--language", help="Original document language")
    parser.add_argument("--item-type", help="Force Zotero item type")
    parser.add_argument("--collection", action="append", default=[], help="Repeatable Zotero collection path")
    parser.add_argument("--tag", action="append", default=[], help="Repeatable Zotero tag")
    parser.add_argument(
        "--target-language",
        default="Simplified Chinese",
        help="Translation target language, default: Simplified Chinese",
    )
    parser.add_argument(
        "--translation-destination",
        choices=["attachment", "note", "both"],
        default="attachment",
        help="Where to save the translation inside Zotero",
    )
    parser.add_argument(
        "--ocr-mode",
        choices=["auto", "always", "never"],
        default="auto",
        help="OCR policy for PDFs. auto tries direct extraction first and falls back to OCR",
    )
    parser.add_argument(
        "--ocr-languages",
        default="en-US,zh-Hans",
        help="Comma-separated OCR languages for the macOS Vision backend",
    )
    parser.add_argument(
        "--max-ocr-pages",
        type=int,
        help="Optional maximum number of pages to OCR or extract from the PDF",
    )
    parser.add_argument("--no-translate", action="store_true", help="Skip translation even if text is available")
    parser.add_argument("--skip-zotero", action="store_true", help="Do not write anything to Zotero")
    parser.add_argument("--output-dir", help="Directory for generated translation files")
    parser.add_argument("--dry-run", action="store_true", help="Resolve inputs and print the plan without writing")
    return parser.parse_args()


def sanitize_filename(value: str, fallback: str = "paper") -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return sanitized[:100] or fallback


def extract_doi(text: str) -> Optional[str]:
    if not text:
        return None
    match = DOI_PATTERN.search(text)
    if not match:
        return None
    return match.group(0).rstrip(").,;]")


def read_url(url: str, binary: bool = False) -> bytes:
    req = request.Request(url, headers={"User-Agent": "codex-zotero-import-translate/1.0"})
    try:
        with request.urlopen(req, timeout=120) as response:
            data = response.read()
            return data if binary else data
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} while fetching {url}: {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error while fetching {url}: {exc}") from exc


def fetch_crossref_metadata(doi: str) -> Dict[str, Any]:
    encoded = parse.quote(doi, safe="")
    raw = read_url(f"https://api.crossref.org/works/{encoded}", binary=True)
    payload = json.loads(raw.decode("utf-8"))
    message = payload.get("message")
    if not message:
        raise RuntimeError(f"Crossref returned no message for DOI {doi}")
    return message


def clean_abstract(raw_abstract: Optional[str]) -> Optional[str]:
    if not raw_abstract:
        return None
    stripped = re.sub(r"<[^>]+>", " ", raw_abstract)
    stripped = html.unescape(stripped)
    stripped = re.sub(r"\s+", " ", stripped).strip()
    return stripped or None


def date_parts_to_string(parts: List[List[int]]) -> Optional[str]:
    if not parts:
        return None
    first = parts[0]
    if not first:
        return None
    values = [str(first[0])]
    if len(first) > 1:
        values.append(f"{first[1]:02d}")
    if len(first) > 2:
        values.append(f"{first[2]:02d}")
    return "-".join(values)


def creators_from_crossref(authors: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    creators: List[Dict[str, str]] = []
    for author in authors or []:
        given = (author.get("given") or "").strip()
        family = (author.get("family") or "").strip()
        name = (author.get("name") or "").strip()
        if given or family:
            creators.append({"creatorType": "author", "firstName": given, "lastName": family})
        elif name:
            creators.append({"creatorType": "author", "name": name})
    return creators


def creators_from_manual(authors: List[str]) -> List[Dict[str, str]]:
    creators: List[Dict[str, str]] = []
    for author in authors:
        author = author.strip()
        if not author:
            continue
        pieces = author.split()
        if len(pieces) >= 2:
            creators.append(
                {
                    "creatorType": "author",
                    "firstName": " ".join(pieces[:-1]),
                    "lastName": pieces[-1],
                }
            )
        else:
            creators.append({"creatorType": "author", "name": author})
    return creators


def choose_item_type(crossref_type: Optional[str], override: Optional[str]) -> str:
    if override:
        return override
    mapping = {
        "journal-article": "journalArticle",
        "article-journal": "journalArticle",
        "proceedings-article": "conferencePaper",
        "book-chapter": "bookSection",
        "book-part": "bookSection",
        "book": "book",
        "monograph": "book",
        "report": "report",
        "dissertation": "thesis",
    }
    return mapping.get((crossref_type or "").lower(), "journalArticle")


def download_pdf(pdf_url: str) -> Path:
    filename = sanitize_filename(Path(parse.urlparse(pdf_url).path).name or "downloaded-paper", fallback="paper")
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    target_dir = Path(tempfile.mkdtemp(prefix="zotero-pdf-"))
    target_path = target_dir / filename
    data = read_url(pdf_url, binary=True)
    target_path.write_bytes(data)
    return target_path


def build_metadata(args: argparse.Namespace, pdf_path: Optional[Path]) -> Dict[str, Any]:
    doi = args.doi or extract_doi(args.url or "")
    front_matter_text = None

    if not doi and pdf_path:
        try:
            front_matter_text = extract_text_from_pdf(
                pdf_path,
                max_pages=min(args.max_ocr_pages or 5, 5) if args.max_ocr_pages else 5,
                ocr_mode=args.ocr_mode,
                ocr_languages=args.ocr_languages,
                min_direct_chars=200,
            )
            doi = extract_doi(front_matter_text)
        except OCRExtractionError as exc:
            log(f"DOI extraction from PDF skipped: {exc}")

    crossref: Dict[str, Any] = {}
    if doi:
        try:
            crossref = fetch_crossref_metadata(doi)
        except RuntimeError as exc:
            log(f"Crossref metadata lookup failed for DOI {doi}: {exc}")

    item_type = choose_item_type(crossref.get("type"), args.item_type)
    fallback_title = pdf_path.stem if pdf_path and args.use_filename_as_fallback_title else None
    if args.text_file and args.use_filename_as_fallback_title:
        fallback_title = Path(args.text_file).expanduser().stem
    title = args.title or "; ".join(crossref.get("title") or []) or fallback_title or None
    if not title:
        raise RuntimeError(
            "Need a title or a DOI that resolves to metadata. Use --title or --use-filename-as-fallback-title."
        )

    creators = creators_from_crossref(crossref.get("author") or [])
    if not creators and args.author:
        creators = creators_from_manual(args.author)

    metadata = {
        "doi": doi,
        "item_type": item_type,
        "title": title,
        "creators": creators,
        "date": args.year or date_parts_to_string((crossref.get("issued") or {}).get("date-parts") or []) or None,
        "container_title": args.journal or "; ".join(crossref.get("container-title") or []) or None,
        "url": args.url or crossref.get("URL") or None,
        "abstract": args.abstract or clean_abstract(crossref.get("abstract")),
        "language": args.language or crossref.get("language") or None,
        "pages": crossref.get("page"),
        "volume": crossref.get("volume"),
        "issue": crossref.get("issue"),
        "publisher": crossref.get("publisher"),
        "crossref_type": crossref.get("type"),
    }
    return metadata


def populate_item_template(
    template: Dict[str, Any], metadata: Dict[str, Any], collection_keys: List[str], tags: List[str]
) -> Dict[str, Any]:
    item = dict(template)
    item["itemType"] = metadata["item_type"]
    item["title"] = metadata["title"]
    item["creators"] = metadata.get("creators") or []
    item["tags"] = [{"tag": tag} for tag in tags]
    item["collections"] = collection_keys
    item["relations"] = {}

    field_map = {
        "DOI": metadata.get("doi"),
        "url": metadata.get("url"),
        "date": metadata.get("date"),
        "abstractNote": metadata.get("abstract"),
        "language": metadata.get("language"),
        "pages": metadata.get("pages"),
        "volume": metadata.get("volume"),
        "issue": metadata.get("issue"),
        "publisher": metadata.get("publisher"),
        "publicationTitle": metadata.get("container_title"),
        "proceedingsTitle": metadata.get("container_title"),
        "bookTitle": metadata.get("container_title"),
        "websiteTitle": metadata.get("container_title"),
        "blogTitle": metadata.get("container_title"),
        "journalAbbreviation": metadata.get("container_title"),
    }
    for field_name, value in field_map.items():
        if value not in (None, "") and field_name in item:
            item[field_name] = value
    return item


def choose_output_dir(args: argparse.Namespace) -> Path:
    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir
    return Path(tempfile.mkdtemp(prefix="zotero-translation-"))


def load_source_text(args: argparse.Namespace, pdf_path: Optional[Path]) -> Optional[str]:
    if args.text_file:
        return Path(args.text_file).expanduser().read_text(encoding="utf-8")
    if pdf_path:
        text = extract_text_from_pdf(
            pdf_path,
            max_pages=args.max_ocr_pages,
            ocr_mode=args.ocr_mode,
            ocr_languages=args.ocr_languages,
            min_direct_chars=500,
        )
        if len(text.strip()) < 500:
            raise RuntimeError(
                "Extracted PDF text is too short. The PDF is likely scanned or image-only and OCR did not recover enough text."
            )
        return text
    return None


def render_translation_markdown(metadata: Dict[str, Any], translated_text: str, target_language: str) -> str:
    lines = [
        f"# {metadata['title']}",
        "",
        f"- Target language: {target_language}",
        f"- Generated at: {datetime.now(timezone.utc).isoformat()}",
    ]
    if metadata.get("doi"):
        lines.append(f"- DOI: {metadata['doi']}")
    if metadata.get("url"):
        lines.append(f"- URL: {metadata['url']}")
    lines.extend(["", "---", "", translated_text.strip(), ""])
    return "\n".join(lines)


def render_translation_note(markdown_text: str) -> str:
    sections = []
    for block in markdown_text.strip().split("\n\n"):
        stripped = block.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            sections.append(f"<h1>{html.escape(stripped[2:].strip())}</h1>")
            continue
        if stripped.startswith("- "):
            items = []
            for line in stripped.splitlines():
                if line.startswith("- "):
                    items.append(f"<li>{html.escape(line[2:].strip())}</li>")
            sections.append(f"<ul>{''.join(items)}</ul>")
            continue
        sections.append(f"<p>{html.escape(stripped).replace(chr(10), '<br/>')}</p>")
    return "".join(sections)


def write_translation_file(output_dir: Path, metadata: Dict[str, Any], markdown_text: str, target_language: str) -> Path:
    slug = sanitize_filename(metadata["title"], fallback="paper")
    language_slug = sanitize_filename(target_language.lower(), fallback="translation")
    path = output_dir / f"{slug}.{language_slug}.md"
    path.write_text(markdown_text, encoding="utf-8")
    return path


def print_plan(metadata: Dict[str, Any], pdf_path: Optional[Path], source_text: Optional[str], args: argparse.Namespace) -> None:
    plan = {
        "title": metadata.get("title"),
        "doi": metadata.get("doi"),
        "item_type": metadata.get("item_type"),
        "container_title": metadata.get("container_title"),
        "collections": args.collection,
        "tags": args.tag,
        "pdf_path": str(pdf_path) if pdf_path else None,
        "text_source": args.text_file or (str(pdf_path) if pdf_path else None),
        "text_characters": len(source_text or ""),
        "translate": bool(source_text and not args.no_translate),
        "translation_destination": args.translation_destination,
        "skip_zotero": args.skip_zotero,
        "ocr_mode": args.ocr_mode,
        "ocr_languages": args.ocr_languages,
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))


def maybe_create_note_stub(client: ZoteroClient, parent_key: str, attachment_name: str, target_language: str) -> None:
    note = (
        f"<h1>{html.escape(target_language)} translation</h1>"
        f"<p>Full translation is stored as the child attachment <strong>{html.escape(attachment_name)}</strong>.</p>"
    )
    client.create_note(parent_key, note)


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.pdf).expanduser().resolve() if args.pdf else None
    if args.pdf_url:
        log(f"Downloading PDF from {args.pdf_url}")
        pdf_path = download_pdf(args.pdf_url)
        log(f"Saved downloaded PDF to {pdf_path}")

    metadata = build_metadata(args, pdf_path)

    source_text = None
    if not args.no_translate:
        try:
            source_text = load_source_text(args, pdf_path)
        except Exception as exc:
            if args.dry_run:
                log(f"Source text unavailable during dry-run: {exc}")
            else:
                raise

    if args.dry_run:
        print_plan(metadata, pdf_path, source_text, args)
        return 0

    client = None
    collection_keys: List[str] = []
    if not args.skip_zotero:
        client = ZoteroClient.from_env()
        for collection in args.collection:
            log(f"Ensuring collection path: {collection}")
            collection_keys.append(client.ensure_collection_path(collection))

    parent_item_key = None
    if client:
        template = client.get_item_template(metadata["item_type"])
        parent_item = populate_item_template(template, metadata, collection_keys, args.tag)
        log(f"Creating Zotero item: {metadata['title']}")
        parent_item_key = client.create_item(parent_item)
        log(f"Created parent item: {parent_item_key}")

        if pdf_path:
            log(f"Uploading source PDF: {pdf_path.name}")
            attachment_key = client.upload_attachment_file(
                parent_item_key,
                pdf_path,
                title="Full Text PDF",
                content_type="application/pdf",
            )
            log(f"Uploaded PDF attachment: {attachment_key}")

    if args.no_translate:
        log("Translation skipped by request")
        return 0

    if not source_text:
        log("No PDF or text source available, so full-text translation was skipped")
        return 0

    def on_progress(index: int, total: int) -> None:
        log(f"Translating chunk {index}/{total}")

    log(f"Starting translation to {args.target_language}")
    translated_text = translate_text(source_text, args.target_language, progress_callback=on_progress)
    markdown_text = render_translation_markdown(metadata, translated_text, args.target_language)
    output_dir = choose_output_dir(args)
    translation_path = write_translation_file(output_dir, metadata, markdown_text, args.target_language)
    log(f"Translation written to {translation_path}")

    if client and parent_item_key:
        if args.translation_destination in {"attachment", "both"} or (
            args.translation_destination == "note" and len(markdown_text) > NOTE_CHAR_LIMIT
        ):
            log("Uploading translated Markdown attachment to Zotero")
            translation_attachment_key = client.upload_attachment_file(
                parent_item_key,
                translation_path,
                title=f"Full-text translation ({args.target_language})",
                content_type="text/markdown",
            )
            log(f"Uploaded translation attachment: {translation_attachment_key}")

        if args.translation_destination in {"note", "both"}:
            if len(markdown_text) <= NOTE_CHAR_LIMIT:
                log("Creating Zotero translation note")
                note_key = client.create_note(parent_item_key, render_translation_note(markdown_text))
                log(f"Created translation note: {note_key}")
            else:
                log("Translation is too large for a full note, creating a stub note instead")
                maybe_create_note_stub(client, parent_item_key, translation_path.name, args.target_language)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ZoteroError, TranslationError, OCRExtractionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
