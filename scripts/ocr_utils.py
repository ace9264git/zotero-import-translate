#!/usr/bin/env python3

import shutil
import subprocess
from pathlib import Path
from typing import Optional


class OCRExtractionError(RuntimeError):
    pass


SCRIPT_DIR = Path(__file__).resolve().parent
SWIFT_OCR_SCRIPT = SCRIPT_DIR / "pdf_ocr.swift"


def _extract_text_with_pypdf(pdf_path: Path, max_pages: Optional[int] = None) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except ImportError:
            return ""

    reader = PdfReader(str(pdf_path))
    pages = reader.pages if max_pages is None else reader.pages[:max_pages]
    text_parts = []
    for page in pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            text_parts.append(extracted)
    return "\n\n".join(text_parts).strip()


def _extract_text_with_swift_vision(pdf_path: Path, max_pages: Optional[int], ocr_languages: str) -> str:
    swift = shutil.which("swift")
    if not swift:
        raise OCRExtractionError("Swift is not installed, so the macOS Vision OCR backend is unavailable")
    if not SWIFT_OCR_SCRIPT.is_file():
        raise OCRExtractionError(f"Swift OCR script not found: {SWIFT_OCR_SCRIPT}")

    cmd = [swift, str(SWIFT_OCR_SCRIPT), "--pdf", str(pdf_path), "--languages", ocr_languages]
    if max_pages:
        cmd.extend(["--max-pages", str(max_pages)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "Unknown OCR failure"
        raise OCRExtractionError(detail)
    return result.stdout.strip()


def extract_text_from_pdf(
    pdf_path: Path,
    *,
    max_pages: Optional[int] = None,
    ocr_mode: str = "auto",
    ocr_languages: str = "en-US,zh-Hans",
    min_direct_chars: int = 500,
) -> str:
    pdf_path = Path(pdf_path).expanduser().resolve()
    if not pdf_path.is_file():
        raise OCRExtractionError(f"PDF file not found: {pdf_path}")

    if ocr_mode not in {"auto", "always", "never"}:
        raise OCRExtractionError(f"Unsupported OCR mode: {ocr_mode}")

    direct_text = ""
    if ocr_mode != "always":
        direct_text = _extract_text_with_pypdf(pdf_path, max_pages=max_pages)
        if ocr_mode == "never":
            if direct_text.strip():
                return direct_text
            raise OCRExtractionError(
                "Direct PDF extraction returned no useful text. Install pypdf or switch to --ocr-mode auto/always."
            )
        if len(direct_text.strip()) >= min_direct_chars:
            return direct_text

    ocr_text = _extract_text_with_swift_vision(pdf_path, max_pages=max_pages, ocr_languages=ocr_languages)
    if len(ocr_text.strip()) >= len(direct_text.strip()):
        return ocr_text
    if direct_text.strip():
        return direct_text
    raise OCRExtractionError("OCR did not recover useful text from the PDF")
