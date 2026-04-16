# 配置说明（中文）

## 1. 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

当前 `requirements.txt` 只包含 `pypdf`，用于文本型 PDF 的直接抽取。即使没安装它，项目仍然可以在 macOS 上走 Swift OCR 回退路径，只是速度更慢。

## 2. 配置 Zotero

```bash
export ZOTERO_API_KEY="你的 Zotero 写入 Key"
export ZOTERO_LIBRARY_TYPE="user"
```

如果目标是群组库：

```bash
export ZOTERO_LIBRARY_ID="1234567"
```

## 3. 配置翻译模型

```bash
export OPENAI_API_KEY="你的模型 Key"
export OPENAI_MODEL="gpt-4.1-mini"
export OPENAI_BASE_URL="https://api.openai.com/v1"
```

如果你使用别的兼容服务，也可以改成：

```bash
export TRANSLATE_API_KEY="你的兼容服务 Key"
export TRANSLATE_MODEL="你的模型名"
export TRANSLATE_BASE_URL="你的兼容接口地址"
```

## 4. OCR 说明

本项目内置 macOS OCR 路径：

- Python 脚本负责调度
- Swift 脚本通过 `PDFKit + Vision` 逐页识别
- 不依赖 `tesseract`

适用前提：

- 运行环境是 macOS
- 系统内可用 `swift`

## 5. 上传 GitHub 前建议

- 检查 `.env`、API key、个人测试输出是否未被提交
- 先运行一遍 `python3 -m py_compile scripts/*.py`
- 如果要公开仓库，确认 `LICENSE` 是否符合你的要求
