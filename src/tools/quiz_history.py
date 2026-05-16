from __future__ import annotations

import re
from datetime import datetime
from typing import Any


QUIZ_HISTORY_VERSION = 1
DEFAULT_HISTORY_LIMIT = 120
VARIANT_SUFFIX_PATTERN = re.compile(r"\s*[\(\[]\s*variant\s*\d+\s*[\)\]]\s*$", re.IGNORECASE)
TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)


def normalize_question_text(text: str) -> str:
    """Normalize question text for duplicate detection."""

    without_variant = VARIANT_SUFFIX_PATTERN.sub("", str(text or "").strip())
    tokens = TOKEN_PATTERN.findall(without_variant.casefold())
    return "".join(tokens)


def quiz_history_scope(course_id: str | None, topic: str) -> str:
    course_key = str(course_id or "legacy").strip().casefold() or "legacy"
    topic_key = normalize_question_text(topic) or "revision"
    return f"{course_key}::{topic_key}"


def quiz_history_avoid_questions(history: Any, *, course_id: str | None, topic: str) -> list[str]:
    if isinstance(history, list):
        return [str(item) for item in history if str(item or "").strip()]

    if not isinstance(history, dict):
        return []

    scope = _scope_payload(history, course_id=course_id, topic=topic)
    if not scope:
        return []

    avoid_questions = []
    for entry in scope.get("questions", []):
        if isinstance(entry, dict):
            text = str(entry.get("text") or entry.get("normalized") or "").strip()
        else:
            text = str(entry or "").strip()
        if text:
            avoid_questions.append(text)
    return avoid_questions


def append_quiz_history(
    history: Any,
    *,
    course_id: str | None,
    topic: str,
    questions: list[dict[str, Any]],
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> dict[str, Any]:
    normalized_history = _coerce_history(history)
    scope_key = quiz_history_scope(course_id, topic)
    scopes = normalized_history.setdefault("scopes", {})
    scope = scopes.setdefault(
        scope_key,
        {
            "course_id": course_id,
            "topic": topic,
            "normalized_topic": normalize_question_text(topic),
            "questions": [],
            "updated_at_utc": None,
        },
    )
    scope["course_id"] = course_id
    scope["topic"] = topic
    scope["normalized_topic"] = normalize_question_text(topic)

    seen = {
        normalize_question_text(str(entry.get("normalized") or entry.get("text") or ""))
        for entry in scope.get("questions", [])
        if isinstance(entry, dict)
    }
    entries = list(scope.get("questions", []))
    for question in questions:
        question_text = str(question.get("question") or "").strip()
        normalized = normalize_question_text(question_text)
        if not question_text or not normalized or normalized in seen:
            continue
        seen.add(normalized)
        entries.append({"text": question_text, "normalized": normalized})

    scope["questions"] = entries[-limit:]
    scope["updated_at_utc"] = datetime.utcnow().isoformat(timespec="seconds")
    normalized_history["scopes"][scope_key] = scope
    return normalized_history


def _coerce_history(history: Any) -> dict[str, Any]:
    if isinstance(history, dict) and isinstance(history.get("scopes"), dict):
        return {
            "version": int(history.get("version") or QUIZ_HISTORY_VERSION),
            "scopes": dict(history.get("scopes") or {}),
        }
    return {"version": QUIZ_HISTORY_VERSION, "scopes": {}}


def _scope_payload(history: dict[str, Any], *, course_id: str | None, topic: str) -> dict[str, Any] | None:
    scopes = history.get("scopes")
    if not isinstance(scopes, dict):
        return None
    scope = scopes.get(quiz_history_scope(course_id, topic))
    return scope if isinstance(scope, dict) else None
