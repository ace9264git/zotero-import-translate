# 使用说明（中文）

## 项目用途

这个项目用于自动完成以下流程：

- 从 DOI、PDF、本地文本导入文献
- 自动创建 Zotero collection 和 tag
- 上传原始 PDF 到 Zotero
- 提取全文并调用大模型翻译
- 把翻译结果作为 note 或 Markdown 附件回写到 Zotero
- 批量处理整个文件夹

## 单篇导入

### 1. DOI + PDF

```bash
python3 scripts/import_and_translate.py \
  --doi 10.1038/nphys1170 \
  --pdf ~/Downloads/paper.pdf \
  --collection "LLM/Reading Queue" \
  --tag translated
```

### 2. 扫描版 PDF OCR

```bash
python3 scripts/import_and_translate.py \
  --pdf ~/Downloads/scanned-paper.pdf \
  --use-filename-as-fallback-title \
  --ocr-mode always \
  --collection "OCR Queue" \
  --tag ocr
```

### 3. 只做翻译，不写入 Zotero

```bash
python3 scripts/import_and_translate.py \
  --title "Temporary Draft" \
  --text-file ./paper.txt \
  --skip-zotero \
  --output-dir ./translated
```

### 4. 先预演，不真正写入

```bash
python3 scripts/import_and_translate.py \
  --pdf ~/Downloads/paper.pdf \
  --use-filename-as-fallback-title \
  --dry-run
```

## 批量导入

```bash
python3 scripts/batch_import.py \
  --input-dir ~/Downloads/papers \
  --recursive \
  --collection "Inbox/Batch Import" \
  --tag batch \
  --continue-on-error \
  --output-dir ./output
```

批量模式会：

- 扫描目录中的 `.pdf`、`.txt`、`.md`
- 对每个文件调用单篇导入脚本
- 在 `output/batch-report.json` 中写入结果报告

## 常用参数

- `--collection`: 可重复传入，支持 `A/B/C` 这种层级路径
- `--tag`: 可重复传入多个 tag
- `--translation-destination attachment|note|both`: 控制翻译结果回写形式
- `--ocr-mode auto|always|never`: 控制 OCR 策略
- `--ocr-languages`: OCR 语言，默认 `en-US,zh-Hans`
- `--max-ocr-pages`: 限制 OCR 页数，适合超长 PDF
- `--use-filename-as-fallback-title`: DOI 和标题都拿不到时，退回使用文件名

## 输出结果

默认情况下：

- Zotero 中会创建父条目
- 原始 PDF 会作为子附件上传
- 翻译结果默认以 Markdown 子附件上传
- 如果使用 `note` 或 `both`，还会创建子 note

## 建议

- 正常英文论文优先使用 `--ocr-mode auto`
- 纯扫描件直接用 `--ocr-mode always`
- 批处理任务建议始终加 `--continue-on-error`
- 上传 GitHub 前，把 `.env` 这种本地私密配置排除掉
