#!/usr/bin/env python3

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
IMPORT_SCRIPT = SCRIPT_DIR / "import_and_translate.py"
DEFAULT_EXTENSIONS = {".pdf", ".txt", ".md"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch import PDFs and text files into Zotero and generate translations."
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing PDFs or text files")
    parser.add_argument(
        "--glob",
        action="append",
        default=[],
        help="Optional glob pattern. Repeatable. Default scans *.pdf, *.txt, and *.md",
    )
    parser.add_argument("--recursive", action="store_true", help="Scan directories recursively")
    parser.add_argument("--collection", action="append", default=[], help="Repeatable Zotero collection path")
    parser.add_argument("--tag", action="append", default=[], help="Repeatable Zotero tag")
    parser.add_argument("--target-language", default="Simplified Chinese")
    parser.add_argument("--translation-destination", choices=["attachment", "note", "both"], default="attachment")
    parser.add_argument("--ocr-mode", choices=["auto", "always", "never"], default="auto")
    parser.add_argument("--ocr-languages", default="en-US,zh-Hans")
    parser.add_argument("--max-ocr-pages", type=int)
    parser.add_argument("--skip-zotero", action="store_true")
    parser.add_argument("--no-translate", action="store_true")
    parser.add_argument("--output-dir", help="Directory for translation markdown files and batch report")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true")
    return parser.parse_args()


def discover_files(root: Path, patterns: List[str], recursive: bool) -> List[Path]:
    files = set()
    if patterns:
        for pattern in patterns:
            iterator = root.rglob(pattern) if recursive else root.glob(pattern)
            files.update(path.resolve() for path in iterator if path.is_file())
    else:
        iterator = root.rglob("*") if recursive else root.glob("*")
        files.update(path.resolve() for path in iterator if path.is_file() and path.suffix.lower() in DEFAULT_EXTENSIONS)
    return sorted(files)


def build_command(args: argparse.Namespace, path: Path) -> List[str]:
    cmd = [sys.executable, str(IMPORT_SCRIPT)]
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        cmd.extend(["--pdf", str(path), "--use-filename-as-fallback-title"])
    else:
        cmd.extend(["--text-file", str(path), "--title", path.stem])

    for collection in args.collection:
        cmd.extend(["--collection", collection])
    for tag in args.tag:
        cmd.extend(["--tag", tag])

    cmd.extend(["--target-language", args.target_language])
    cmd.extend(["--translation-destination", args.translation_destination])
    cmd.extend(["--ocr-mode", args.ocr_mode])
    cmd.extend(["--ocr-languages", args.ocr_languages])

    if args.max_ocr_pages:
        cmd.extend(["--max-ocr-pages", str(args.max_ocr_pages)])
    if args.skip_zotero:
        cmd.append("--skip-zotero")
    if args.no_translate:
        cmd.append("--no-translate")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.output_dir:
        output_root = Path(args.output_dir).expanduser().resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        per_file_dir = output_root / path.stem
        per_file_dir.mkdir(parents=True, exist_ok=True)
        cmd.extend(["--output-dir", str(per_file_dir)])
    return cmd


def write_report(report_path: Path, entries: List[Dict[str, str]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    input_dir = Path(args.input_dir).expanduser().resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"ERROR: Input directory not found: {input_dir}")

    files = discover_files(input_dir, args.glob, args.recursive)
    if not files:
        raise SystemExit(f"ERROR: No matching files found in {input_dir}")

    print(f"Discovered {len(files)} files under {input_dir}", file=sys.stderr)
    report_entries: List[Dict[str, str]] = []

    for index, path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] Processing {path}", file=sys.stderr)
        cmd = build_command(args, path)
        result = subprocess.run(cmd, capture_output=True, text=True)
        entry = {
            "file": str(path),
            "status": "success" if result.returncode == 0 else "failed",
            "returncode": str(result.returncode),
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
        report_entries.append(entry)
        if result.returncode != 0 and not args.continue_on_error:
            if args.output_dir:
                write_report(Path(args.output_dir).expanduser().resolve() / "batch-report.json", report_entries)
            raise SystemExit(result.returncode)

    if args.output_dir:
        write_report(Path(args.output_dir).expanduser().resolve() / "batch-report.json", report_entries)

    failures = sum(1 for entry in report_entries if entry["status"] != "success")
    successes = len(report_entries) - failures
    print(f"Batch finished: {successes} succeeded, {failures} failed", file=sys.stderr)
    return 0 if failures == 0 or args.continue_on_error else 1


if __name__ == "__main__":
    raise SystemExit(main())
