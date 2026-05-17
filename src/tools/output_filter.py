from __future__ import annotations

import re
import unicodedata

from src.localization import detect_language, normalize_language, t

# Leakage / internal-instruction markers (normalized casefold matching).
_LEAKAGE_MARKERS: tuple[str, ...] = (
    "system prompt:",
    "the system prompt is",
    "your system prompt",
    "reveal the system prompt",
    "hidden instructions",
    "developer instructions",
    "you are a helpful assistant",
    "you are chatgpt",
    "role: system",
    "system message:",
    "التعليمات المخفية",
    "البرومبت السري",
    "رسالة النظام",
)

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\baccess_token\s*[:=]\s*\S+"),
    re.compile(r"(?i)\brefresh_token\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(?:api[_-]?key|gemini_api_key)\s*[:=]\s*\S+"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b"),
    re.compile(r"\beyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9._-]+\b"),
)

_STACK_TRACE = re.compile(
    r"(?is)(?:traceback \(most recent call last\):|file \"[^\"]+\", line \d+)"
)
_INTERNAL_PATH = re.compile(
    r"(?i)(?:"
    r"[a-z]:\\(?:users|home|gen-ai|rafeeqak|smart-study-planner|\.venv|src)[^ \n\r\t]*|"
    r"/(?:home|var|users|tmp|opt)/[^\s]+|"
    r"(?:^|\s)[^\s]*(?:\\|/)(?:src|\.venv|node_modules)(?:\\|/)[^\s]+"
    r")"
)
_RAW_CHUNK_JSON = re.compile(r'"\s*(?:chunk_index|source_name|score)\s*"\s*:\s*', re.IGNORECASE)
_LONG_LINE = 400


def _normalize_screening_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = re.sub(r"[\u200b-\u200f\ufeff]", "", normalized)
    normalized = re.sub(r"[\u064b-\u065f\u0670]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold()


def _resolve_fallback_language(language: str, text: str) -> str:
    lang = normalize_language(language)
    if lang == "ar" or detect_language(text) == "ar":
        return "ar"
    return lang


def _fallback_message(language: str, *, text: str = "") -> str:
    return t("agent.output_filtered", _resolve_fallback_language(language, text))


def _is_empty(response: str) -> bool:
    return not str(response or "").strip()


def _has_leakage(text: str) -> bool:
    normalized = _normalize_screening_text(text)
    return any(marker in normalized for marker in _LEAKAGE_MARKERS)


def _has_stack_trace(text: str) -> bool:
    return bool(_STACK_TRACE.search(text))


def _has_internal_path(text: str) -> bool:
    if _INTERNAL_PATH.search(text):
        return True
    # Absolute Windows paths outside short citation filenames.
    if re.search(r"(?i)\b[a-z]:\\[^\s]{8,}", text):
        return True
    return False


def _has_excessive_raw_chunks(text: str) -> bool:
    if _RAW_CHUNK_JSON.search(text):
        return True
    long_lines = [line for line in text.splitlines() if len(line.strip()) > _LONG_LINE]
    return len(long_lines) >= 3


def _redact_secrets(text: str) -> tuple[str, bool]:
    redacted = text
    changed = False
    for pattern in _SECRET_PATTERNS:
        updated, count = pattern.subn("[REDACTED]", redacted)
        if count:
            changed = True
            redacted = updated
    return redacted, changed


def _should_block_entirely(text: str) -> bool:
    return (
        _has_leakage(text)
        or _has_stack_trace(text)
        or _has_internal_path(text)
        or _has_excessive_raw_chunks(text)
    )


def filter_output(response: str, language: str) -> str:
    """Sanitize assistant text before it is shown in the UI."""
    if _is_empty(response):
        return _fallback_message(language)

    text = str(response)
    if _should_block_entirely(text):
        return _fallback_message(language, text=text)

    redacted, changed = _redact_secrets(text)
    if changed:
        if _should_block_entirely(redacted):
            return _fallback_message(language, text=text)
        return redacted

    return text
