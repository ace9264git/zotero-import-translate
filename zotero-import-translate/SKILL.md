---
name: zotero-import-translate
description: Import literature/papers (文献) into Zotero from DOI, DOI URLs, local PDFs, PDF URLs, directories of files, or plain-text files, create collections and tags, attach files, run OCR on scanned PDFs, and generate full-text translations (全文翻译) saved back to Zotero as notes or attachments. Use when Codex needs to automate Zotero ingestion, bulk-add papers, process scanned or image-only PDFs, attach PDFs, or translate an article's full text into Simplified Chinese for reading, annotation, or review prep.
---

# Zotero Import Translate

## Overview

Use the bundled scripts to ingest a paper into Zotero through the official Zotero Web API, upload the source PDF, extract text from native or scanned PDFs, translate the full text, and write the translation back to Zotero.

Prefer the end-to-end entrypoint `scripts/import_and_translate.py` for one paper and `scripts/batch_import.py` for a directory. Read `references/setup.md` when environment variables, OCR behavior, or batch workflow details are unclear.

## Default Workflow

1. Prefer `DOI + PDF` as the default input pair.
2. If the user provides only a PDF, let the script try DOI extraction from the first pages before falling back to the filename.
3. Use `--ocr-mode auto` by default. It tries direct text extraction first and falls back to macOS Vision OCR for scanned PDFs.
4. Default translation output to a Markdown attachment in Zotero. Use `--translation-destination note` or `both` only when the user explicitly wants the translation inline as a child note.
5. Default the target language to Simplified Chinese unless the user asks for another language.
6. Use `scripts/batch_import.py` for a folder of PDFs or text files instead of writing a custom loop.

## Run The Skill

Single-paper import:

```bash
python3 ~/.codex/skills/zotero-import-translate/scripts/import_and_translate.py \
  --doi 10.1038/nphys1170 \
  --pdf ~/Downloads/paper.pdf \
  --collection "LLM/Reading Queue" \
  --tag physics \
  --tag translated
```

Scanned PDF with OCR:

```bash
python3 ~/.codex/skills/zotero-import-translate/scripts/import_and_translate.py \
  --pdf ~/Downloads/scanned-paper.pdf \
  --use-filename-as-fallback-title \
  --ocr-mode always \
  --collection "OCR Queue"
```

Batch import a folder:

```bash
python3 ~/.codex/skills/zotero-import-translate/scripts/batch_import.py \
  --input-dir ~/Downloads/papers \
  --recursive \
  --collection "Inbox/Batch Import" \
  --tag batch
```

Translate plain text without writing to Zotero:

```bash
python3 ~/.codex/skills/zotero-import-translate/scripts/import_and_translate.py \
  --title "Local Text Draft" \
  --text-file ./paper.txt \
  --skip-zotero \
  --output-dir ./translated
```

Inspect the planned metadata and translation inputs before any write:

```bash
python3 ~/.codex/skills/zotero-import-translate/scripts/import_and_translate.py \
  --pdf ~/Downloads/paper.pdf \
  --use-filename-as-fallback-title \
  --dry-run
```

## Operating Rules

- Use `scripts/import_and_translate.py` instead of reimplementing Zotero API calls ad hoc.
- Use `scripts/batch_import.py` for directory jobs and preserve the generated batch report.
- Keep imports idempotent at the workflow level: if metadata import succeeds and translation later fails, keep the Zotero item and report the partial completion rather than trying to roll it back.
- Create collection paths before creating the parent item so the parent item can be filed immediately.
- Skip translation with an explicit message when there is no PDF or text source.
- Treat OCR as a fallback for image-only PDFs. Do not force OCR on text PDFs unless the direct extraction is clearly broken.
- Prefer `--pdf-url` only for directly downloadable PDFs. Do not scrape publisher landing pages in this skill.
- Use `--skip-zotero` for translation-only tasks or validation runs that should not modify the library.

## Resources

### scripts/

- `import_and_translate.py`: end-to-end CLI for metadata resolution, Zotero import, PDF upload, OCR/text extraction, translation, and translation write-back.
- `batch_import.py`: directory-oriented wrapper that runs the single-item importer across many files and writes a report.
- `ocr_utils.py`: OCR-aware PDF extraction helper with direct extraction and macOS Vision fallback.
- `pdf_ocr.swift`: macOS-native OCR script built on PDFKit and Vision.
- `zotero_client.py`: minimal Zotero Web API client covering item creation, collection creation, notes, and file uploads.
- `llm_translate.py`: OpenAI-compatible chunked full-text translator with retry handling.

### references/

- `setup.md`: environment variables, dependency setup, OCR behavior, and known limitations.
