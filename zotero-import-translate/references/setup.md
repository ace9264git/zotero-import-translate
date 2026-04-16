# Setup / 配置

## Environment Variables / 环境变量

Set Zotero credentials before writing to the library:

在写入 Zotero 之前先设置凭证：

```bash
export ZOTERO_API_KEY="your-zotero-write-key"
export ZOTERO_LIBRARY_TYPE="user"
```

For group libraries, also set:

如果写入群组库，再补充：

```bash
export ZOTERO_LIBRARY_ID="1234567"
```

Translation uses an OpenAI-compatible Chat Completions endpoint:

翻译使用兼容 OpenAI Chat Completions 的接口：

```bash
export TRANSLATE_API_KEY="your-llm-key"
export TRANSLATE_MODEL="gpt-4.1-mini"
export TRANSLATE_BASE_URL="https://api.openai.com/v1"
```

Or use common OpenAI variables:

或者直接复用常见的 OpenAI 环境变量：

```bash
export OPENAI_API_KEY="your-llm-key"
export OPENAI_MODEL="gpt-4.1-mini"
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

Optional tuning:

可选调优参数：

```bash
export TRANSLATE_CHUNK_CHARS="12000"
export TRANSLATE_TIMEOUT_SECONDS="300"
export TRANSLATE_TEMPERATURE="0.2"
```

## Python Dependency / Python 依赖

Install `pypdf` for better direct extraction from text PDFs:

为文本型 PDF 安装 `pypdf`，可以显著提升直接抽取效果：

```bash
python3 -m pip install -r requirements.txt
```

Without `pypdf`, the project can still:

没有 `pypdf` 时，项目仍然可以：

- import metadata into Zotero / 导入元数据到 Zotero
- upload PDFs to Zotero / 上传 PDF 到 Zotero
- translate plain-text files with `--text-file` / 翻译 `--text-file` 提供的纯文本
- OCR PDFs on macOS through the bundled Swift script / 在 macOS 上通过内置 Swift 脚本执行 OCR

## OCR Behavior / OCR 行为

The project supports three OCR modes:

项目支持三种 OCR 模式：

- `auto`: use direct extraction first, then fall back to macOS Vision OCR
- `always`: force OCR even if direct extraction might work
- `never`: use direct extraction only

默认语言是 `en-US,zh-Hans`。如果文献主要是英文，可以保持默认；如果是中文扫描稿，也建议保留 `zh-Hans`。

## Input Strategy / 输入策略

Prefer inputs in this order:

建议按以下优先级提供输入：

1. `--doi` + `--pdf`
2. `--url` containing a DOI + `--pdf`
3. `--pdf` only and let the script attempt DOI extraction
4. `--pdf` + `--use-filename-as-fallback-title`
5. `--title` + `--text-file`

## Batch Strategy / 批量策略

Use `scripts/batch_import.py` for folders of PDFs or text files.

如果要处理整个文件夹，使用 `scripts/batch_import.py`。

Recommended flags:

推荐参数：

- `--recursive` for nested folders / 递归处理子目录
- `--continue-on-error` for long jobs / 长任务建议遇错继续
- `--output-dir` to keep translation files and the batch report together / 用于统一保存翻译结果和批处理报告

## Limits / 限制

- The Zotero path uses the official web API, so the target library must sync with zotero.org.
- Image-only PDFs still depend on OCR quality. Bad scans will produce bad text.
- DOI metadata is resolved via Crossref. If metadata is incomplete, pass manual fields such as `--title` and `--author`.
- `--pdf-url` is intended for direct file URLs. It is not a general webpage importer.
