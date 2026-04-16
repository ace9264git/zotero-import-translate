# Usage Guide (English)

## What This Project Does

This project automates the following workflow:

- import papers from DOI, PDF, or plain text
- create Zotero collections and tags
- upload the source PDF into Zotero
- extract full text and translate it with an LLM
- write the translation back to Zotero as a note or Markdown attachment
- batch-process a whole directory

## Single Item Import

### 1. DOI + PDF

```bash
python3 scripts/import_and_translate.py \
  --doi 10.1038/nphys1170 \
  --pdf ~/Downloads/paper.pdf \
  --collection "LLM/Reading Queue" \
  --tag translated
```

### 2. Scanned PDF with OCR

```bash
python3 scripts/import_and_translate.py \
  --pdf ~/Downloads/scanned-paper.pdf \
  --use-filename-as-fallback-title \
  --ocr-mode always \
  --collection "OCR Queue" \
  --tag ocr
```

### 3. Translation Only

```bash
python3 scripts/import_and_translate.py \
  --title "Temporary Draft" \
  --text-file ./paper.txt \
  --skip-zotero \
  --output-dir ./translated
```

### 4. Dry Run

```bash
python3 scripts/import_and_translate.py \
  --pdf ~/Downloads/paper.pdf \
  --use-filename-as-fallback-title \
  --dry-run
```

## Batch Import

```bash
python3 scripts/batch_import.py \
  --input-dir ~/Downloads/papers \
  --recursive \
  --collection "Inbox/Batch Import" \
  --tag batch \
  --continue-on-error \
  --output-dir ./output
```

Batch mode will:

- scan `.pdf`, `.txt`, and `.md` files
- invoke the single-item importer for each file
- write a job report to `output/batch-report.json`

## Useful Flags

- `--collection`: repeatable, supports nested paths such as `A/B/C`
- `--tag`: repeatable
- `--translation-destination attachment|note|both`: control how translations are written back
- `--ocr-mode auto|always|never`: control OCR behavior
- `--ocr-languages`: OCR languages, default `en-US,zh-Hans`
- `--max-ocr-pages`: limit extraction or OCR to the first N pages
- `--use-filename-as-fallback-title`: fall back to the filename when DOI metadata is unavailable

## Expected Output

By default, the workflow creates:

- a parent Zotero item
- a child PDF attachment
- a translated Markdown attachment
- optionally a child note when `note` or `both` is used

## Practical Advice

- Use `--ocr-mode auto` for normal academic PDFs.
- Use `--ocr-mode always` for scanned papers.
- Use `--continue-on-error` for long batch jobs.
- Keep local secrets such as `.env` out of your GitHub upload.
