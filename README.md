# Zotero Import Translate

Bilingual Codex skill and GitHub-ready project for importing papers into Zotero, attaching PDFs, running OCR on scanned files, and generating full-text translations.

用于将文献导入 Zotero、附加 PDF、对扫描件执行 OCR，并生成全文翻译。

## Quick Links

- 中文使用文档: [docs/USAGE.zh-CN.md](docs/USAGE.zh-CN.md)
- English usage guide: [docs/USAGE.en.md](docs/USAGE.en.md)
- 中文配置说明: [docs/SETUP.zh-CN.md](docs/SETUP.zh-CN.md)
- English setup guide: [docs/SETUP.en.md](docs/SETUP.en.md)

## Features

- Import papers into Zotero from DOI, DOI URL, local PDF, direct PDF URL, or plain text.
- Create Zotero collections and tags automatically.
- Upload source PDFs and translated Markdown back to Zotero.
- Translate full text through an OpenAI-compatible API.
- Run OCR on scanned PDFs through the bundled macOS `Vision + PDFKit` Swift script.
- Batch-process a whole folder of PDFs and text files.

## Repository Layout

```text
.
├── SKILL.md
├── agents/openai.yaml
├── docs/
├── references/
├── scripts/
├── .env.example
├── .gitignore
├── LICENSE
└── requirements.txt
```

## Quick Start

1. Install Python dependency:

   ```bash
   python3 -m pip install -r requirements.txt
   ```

2. Configure environment variables:

   ```bash
   export ZOTERO_API_KEY="your-zotero-write-key"
   export ZOTERO_LIBRARY_TYPE="user"
   export OPENAI_API_KEY="your-openai-compatible-key"
   export OPENAI_MODEL="gpt-4.1-mini"
   ```

3. Run a single import:

   ```bash
   python3 scripts/import_and_translate.py \
     --doi 10.1038/nphys1170 \
     --pdf ~/Downloads/paper.pdf \
     --collection "Reading Queue" \
     --tag translated
   ```

4. Run batch mode:

   ```bash
   python3 scripts/batch_import.py \
     --input-dir ~/Downloads/papers \
     --recursive \
     --collection "Inbox/Batch Import" \
     --tag batch \
     --continue-on-error \
     --output-dir ./output
   ```

## Notes

- The OCR fallback is macOS-specific because it uses Apple Vision and PDFKit through Swift.
- The Zotero workflow uses the official Zotero Web API, so your target library must sync to zotero.org.
- This repository doubles as a Codex skill folder and as a standalone GitHub project.
