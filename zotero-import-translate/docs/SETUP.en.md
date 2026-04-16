# Setup Guide (English)

## 1. Install Dependencies

```bash
python3 -m pip install -r requirements.txt
```

`requirements.txt` currently includes `pypdf` for direct extraction from text PDFs. Even without it, the project can still fall back to the bundled macOS Swift OCR path, though that path is slower.

## 2. Configure Zotero

```bash
export ZOTERO_API_KEY="your Zotero write key"
export ZOTERO_LIBRARY_TYPE="user"
```

For a group library:

```bash
export ZOTERO_LIBRARY_ID="1234567"
```

## 3. Configure the Translation Model

```bash
export OPENAI_API_KEY="your model key"
export OPENAI_MODEL="gpt-4.1-mini"
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

For another OpenAI-compatible provider, you can also use:

```bash
export TRANSLATE_API_KEY="your provider key"
export TRANSLATE_MODEL="your model name"
export TRANSLATE_BASE_URL="your compatible endpoint"
```

## 4. OCR Notes

This repository includes a macOS-native OCR path:

- Python dispatches the extraction strategy
- Swift performs page rendering and OCR through `PDFKit + Vision`
- no `tesseract` dependency is required

Requirements:

- macOS
- `swift` available in the system

## 5. Before Uploading to GitHub

- make sure `.env`, API keys, and local test outputs are not committed
- run `python3 -m py_compile scripts/*.py`
- confirm that the included `LICENSE` matches your intended distribution
