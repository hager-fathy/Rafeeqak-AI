from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.localization import detect_language

# Normalized substrings that indicate prompt-injection attempts (English and Arabic).
_INJECTION_MARKERS: tuple[str, ...] = (
    "ignore previous instructions",
    "ignore all previous instructions",
    "forget all instructions",
    "forget your instructions",
    "reveal system prompt",
    "reveal the system prompt",
    "show hidden prompt",
    "show the hidden prompt",
    "bypass safety",
    "disable guardrails",
    "disable the guardrails",
    "act as developer",
    "act as a developer",
    "act as system",
    "act as the system",
    "jailbreak",
    "تجاهل التعليمات",
    "تجاهل تعليمات",
    "انس التعليمات",
    "انسى التعليمات",
    "اكشف البرومبت",
    "اكشف البرومت",
    "اكشف التعليمات",
    "تخطى القيود",
    "تخطي القيود",
    "اعمل نفسك system",
    "اعمل نفسك سستم",
)

_ARABIC_DIACRITICS = re.compile(r"[\u064b-\u065f\u0670]")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\ufeff]")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class SafetyResult:
    safe: bool
    flagged: bool
    safety_status: str
    matched_patterns: tuple[str, ...]
    language: str


def _normalize_screening_text(text: str) -> str:
    """Case-fold and lightly normalize Arabic/English text for marker matching."""
    normalized = unicodedata.normalize("NFKC", str(text or ""))
    normalized = _ZERO_WIDTH.sub("", normalized).replace("\u0640", "")
    normalized = _ARABIC_DIACRITICS.sub("", normalized)
    for source, target in (
        ("\u0623", "\u0627"),  # أ -> ا
        ("\u0625", "\u0627"),  # إ -> ا
        ("\u0622", "\u0627"),  # آ -> ا
        ("\u0649", "\u064a"),  # ى -> ي
    ):
        normalized = normalized.replace(source, target)
    normalized = _WHITESPACE.sub(" ", normalized).strip()
    return normalized.casefold()


def detect_prompt_injection(user_text: str) -> SafetyResult:
    """Return whether user_text looks like a prompt-injection attempt."""
    language = detect_language(user_text)
    normalized = _normalize_screening_text(user_text)
    matched = tuple(marker for marker in _INJECTION_MARKERS if marker in normalized)
    flagged = bool(matched)
    return SafetyResult(
        safe=not flagged,
        flagged=flagged,
        safety_status="blocked" if flagged else "passed",
        matched_patterns=matched,
        language=language,
    )


class SafetyAgent:
    """Lightweight prompt-injection screen for unsafe routing requests."""

    def check(self, user_message: str) -> dict:
        result = detect_prompt_injection(user_message)
        return {
            "safe": result.safe,
            "flagged": result.flagged,
            "safety_status": result.safety_status,
            "matched_patterns": list(result.matched_patterns),
            "language": result.language,
        }
