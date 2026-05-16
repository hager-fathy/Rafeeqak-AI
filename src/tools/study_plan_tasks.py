from __future__ import annotations

import hashlib
import re
from typing import Any

from src.localization import t


def is_quiz_task(task: dict[str, Any]) -> bool:
    if not isinstance(task, dict):
        return False
    if str(task.get("task_type") or "").strip().casefold() == "quiz":
        return True
    if task.get("quiz_required") is True or task.get("checkpoint") is True:
        return True
    phase = str(task.get("phase") or "").casefold()
    if "quiz" in phase or "checkpoint" in phase:
        return True
    task_text = str(task.get("task") or "").casefold()
    return "quiz" in task_text


def sync_quiz_required(task: dict[str, Any]) -> None:
    if not isinstance(task, dict):
        return
    if "quiz_required" not in task:
        task["quiz_required"] = bool(task.get("checkpoint"))


def build_task_id(task: dict[str, Any], course_scope: str | None) -> str:
    existing = str(task.get("task_id") or "").strip()
    if existing:
        return existing
    parts = [
        str(course_scope or task.get("course") or "").strip(),
        str(task.get("date") or "").strip(),
        str(task.get("topic") or "").strip(),
        str(task.get("phase") or "").strip(),
        str(task.get("task") or "").strip(),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"task-{digest}"


def ensure_task_ids(plan: dict[str, Any], course_scope: str | None) -> None:
    tasks = plan.get("tasks", [])
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if not isinstance(task, dict):
            continue
        sync_quiz_required(task)
        task["task_id"] = build_task_id(task, course_scope)


def quiz_required_label(task: dict[str, Any], language: str) -> str:
    sync_quiz_required(task)
    if is_quiz_task(task):
        return t("planner.quiz_required.yes", language)
    return t("planner.quiz_required.no", language)


def mark_done_hint(task: dict[str, Any], language: str) -> str:
    if not is_quiz_task(task):
        return ""
    if task.get("completed"):
        return t("planner.mark_done.completed_after_quiz", language)
    return t("planner.mark_done.take_quiz", language)


def tasks_to_timeline_rows(tasks: list[dict[str, Any]], *, language: str, course_scope: str | None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        sync_quiz_required(task)
        task_id = build_task_id(task, course_scope)
        task["task_id"] = task_id
        task.setdefault("completed", False)
        rows.append(
            {
                "task_id": task_id,
                "date": task.get("date", ""),
                "topic": task.get("topic", ""),
                "phase": task.get("phase", ""),
                "task": task.get("task", ""),
                "hours": task.get("hours", 0),
                "quiz_required_label": quiz_required_label(task, language),
                "mark_as_done": bool(task.get("completed")),
                "completion_note": mark_done_hint(task, language),
            }
        )
    return rows


def apply_manual_completion_updates(
    active_plan: dict[str, Any],
    edited_rows: list[dict[str, Any]],
    *,
    course_scope: str | None,
) -> bool:
    tasks = active_plan.get("tasks", [])
    if not isinstance(tasks, list):
        return False

    task_by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        sync_quiz_required(task)
        task_id = build_task_id(task, course_scope)
        task["task_id"] = task_id
        task_by_id[task_id] = task

    changed = False
    for row in edited_rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "").strip()
        if not task_id:
            continue
        task = task_by_id.get(task_id)
        if task is None or is_quiz_task(task):
            continue
        edited_completed = bool(row.get("mark_as_done"))
        if bool(task.get("completed")) != edited_completed:
            task["completed"] = edited_completed
            changed = True
    return changed


def _normalize_topic(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def _topic_matches(task_topic: str, quiz_topic: str) -> bool:
    left = _normalize_topic(task_topic)
    right = _normalize_topic(quiz_topic)
    if not left or not right:
        return False
    return left == right or left in right or right in left


def mark_matching_quiz_task_completed(
    active_plan: dict[str, Any],
    *,
    course_scope: str | None,
    topic: str,
) -> bool:
    tasks = active_plan.get("tasks", [])
    if not isinstance(tasks, list):
        return False

    candidates: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict) or not is_quiz_task(task) or task.get("completed"):
            continue
        if _topic_matches(str(task.get("topic") or ""), topic):
            candidates.append(task)

    if not candidates:
        for task in tasks:
            if not isinstance(task, dict) or not is_quiz_task(task) or task.get("completed"):
                continue
            candidates.append(task)

    if not candidates:
        return False

    def _sort_key(task: dict[str, Any]) -> tuple[int, str]:
        phase = str(task.get("phase") or "").casefold()
        priority = 0 if "checkpoint" in phase or task.get("checkpoint") else 1
        return priority, str(task.get("date") or "")

    target = sorted(candidates, key=_sort_key)[0]
    if target.get("completed"):
        return False
    target["completed"] = True
    return True


def same_plan_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        isinstance(left, dict)
        and left.get("course_name") == right.get("course_name")
        and left.get("exam_date") == right.get("exam_date")
        and len(left.get("tasks", []) or []) == len(right.get("tasks", []) or [])
    )


def sync_active_plan_history(active_plan: dict[str, Any], study_plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for index in range(len(study_plans) - 1, -1, -1):
        plan = study_plans[index]
        if plan is active_plan or same_plan_identity(plan, active_plan):
            study_plans[index] = active_plan
            return study_plans
    return study_plans
