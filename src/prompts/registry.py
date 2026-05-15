from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


TEMPLATE_VARIABLES: dict[str, set[str]] = {
    "course_question": {"course_name", "question", "language"},
    "rag_answer": {"course_name", "question", "context", "citations", "language"},
    "lecture_summary": {"course_name", "lecture_title", "lecture_text", "language"},
    "quiz_generation": {
        "course_name",
        "topic",
        "difficulty",
        "number_of_questions",
        "question_types",
        "context",
        "language",
    },
    "progress_feedback": {"course_name", "score", "weak_topics", "recommendations", "language"},
    "study_planning": {
        "course_name",
        "difficulty",
        "exam_deadline",
        "daily_hours",
        "progress",
        "weak_topics",
        "language",
    },
}


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str


def available_templates() -> tuple[str, ...]:
    return tuple(sorted(TEMPLATE_VARIABLES))


def required_variables(template_name: str) -> set[str]:
    _ensure_known_template(template_name)
    return set(TEMPLATE_VARIABLES[template_name])


def render_prompt(template_name: str, **variables: Any) -> Prompt:
    _ensure_known_template(template_name)
    missing = TEMPLATE_VARIABLES[template_name] - set(variables)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Missing prompt variable(s) for {template_name}: {missing_list}")

    return Prompt(
        system=_render(_load_template(template_name, "system"), variables),
        user=_render(_load_template(template_name, "user"), variables),
    )


def _ensure_known_template(template_name: str) -> None:
    if template_name not in TEMPLATE_VARIABLES:
        raise KeyError(f"Unknown prompt template: {template_name}")


@lru_cache(maxsize=None)
def _load_template(template_name: str, part: str) -> str:
    template_path = Path(__file__).with_name("templates") / f"{template_name}.{part}.txt"
    return template_path.read_text(encoding="utf-8").strip()


def _render(template: str, variables: dict[str, Any]) -> str:
    rendered = template
    for name, value in variables.items():
        rendered = rendered.replace(f"{{{{{name}}}}}", _stringify(value))
    return rendered


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_stringify(item) for item in value)
    return str(value)
