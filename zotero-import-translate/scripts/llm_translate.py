#!/usr/bin/env python3

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Callable, List, Optional
from urllib import error, request


class TranslationError(RuntimeError):
    pass


@dataclass
class TranslationConfig:
    api_key: str
    model: str
    base_url: str
    chunk_chars: int
    timeout_seconds: int
    temperature: float


def load_translation_config() -> TranslationConfig:
    api_key = os.environ.get("TRANSLATE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise TranslationError("Missing TRANSLATE_API_KEY or OPENAI_API_KEY")

    model = os.environ.get("TRANSLATE_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-4.1-mini"
    base_url = (
        os.environ.get("TRANSLATE_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or os.environ.get("OPENAI_API_BASE")
        or "https://api.openai.com/v1"
    )
    chunk_chars = int(os.environ.get("TRANSLATE_CHUNK_CHARS", "12000"))
    timeout_seconds = int(os.environ.get("TRANSLATE_TIMEOUT_SECONDS", "300"))
    temperature = float(os.environ.get("TRANSLATE_TEMPERATURE", "0.2"))
    return TranslationConfig(
        api_key=api_key,
        model=model,
        base_url=base_url.rstrip("/"),
        chunk_chars=chunk_chars,
        timeout_seconds=timeout_seconds,
        temperature=temperature,
    )


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"-\n(?=\w)", "", normalized)
    normalized = re.sub(r"(?<!\n)\n(?!\n)", " ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_text(text: str, max_chars: int) -> List[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: List[str] = []
    current = ""

    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""

        if len(paragraph) <= max_chars:
            current = paragraph
            continue

        for offset in range(0, len(paragraph), max_chars):
            pieces = paragraph[offset : offset + max_chars].strip()
            if pieces:
                chunks.append(pieces)

    if current:
        chunks.append(current)

    if not chunks and text.strip():
        chunks.append(text.strip())
    return chunks


def _extract_message_text(payload: dict) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise TranslationError(f"Translation response contained no choices: {json.dumps(payload)[:500]}")
    content = (choices[0].get("message") or {}).get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return "".join(parts).strip()
    raise TranslationError(f"Unsupported translation response format: {json.dumps(payload)[:500]}")


def _translate_chunk(config: TranslationConfig, chunk: str, target_language: str, chunk_index: int, total_chunks: int) -> str:
    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a precise academic translator. Translate the user's text completely into the "
                    "requested target language. Preserve structure, headings, lists, citations, equations, "
                    "table labels, and technical terms. Do not summarize. Do not add commentary. Return only the translation."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Target language: {target_language}\n"
                    f"Chunk {chunk_index} of {total_chunks}.\n"
                    "Translate the following text in full:\n\n"
                    f"{chunk}"
                ),
            },
        ],
    }

    req = request.Request(
        f"{config.base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "codex-zotero-import-translate/1.0",
        },
    )

    last_error: Optional[Exception] = None
    for attempt in range(1, 4):
        try:
            with request.urlopen(req, timeout=config.timeout_seconds) as response:
                body = response.read()
                data = json.loads(body.decode("utf-8"))
                return _extract_message_text(data)
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = TranslationError(
                f"Translation API {exc.code} on chunk {chunk_index}/{total_chunks}: {body}"
            )
            if exc.code in {429, 500, 502, 503, 504} and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            break
        except error.URLError as exc:
            last_error = TranslationError(f"Translation API network error on chunk {chunk_index}/{total_chunks}: {exc}")
            if attempt < 3:
                time.sleep(2 ** attempt)
                continue
            break

    assert last_error is not None
    raise last_error


def translate_text(
    text: str,
    target_language: str = "Simplified Chinese",
    *,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> str:
    config = load_translation_config()
    normalized = normalize_text(text)
    if not normalized:
        raise TranslationError("No text available for translation")
    chunks = split_text(normalized, config.chunk_chars)
    translated_chunks: List[str] = []

    for index, chunk in enumerate(chunks, start=1):
        if progress_callback:
            progress_callback(index, len(chunks))
        translated_chunks.append(_translate_chunk(config, chunk, target_language, index, len(chunks)))

    return "\n\n".join(part.strip() for part in translated_chunks if part.strip()).strip()
