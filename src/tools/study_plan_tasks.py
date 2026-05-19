from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Any

from src.localization import t

COMPLETIONS_FIELD = "task_completions"


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


def make_task_id(course_id: str, task: dict[str, Any]) -> str:
    """Stable task identifier scoped to a course."""
    return build_task_id(task, course_id)


def get_task_completions(plan: dict[str, Any]) -> dict[str, bool]:
    if not isinstance(plan, dict):
        return {}
    raw = plan.get(COMPLETIONS_FIELD)
    if not isinstance(raw, dict):
        raw = {}
        plan[COMPLETIONS_FIELD] = raw
    return raw


def is_task_completed(task: dict[str, Any], plan: dict[str, Any] | None = None) -> bool:
    if not isinstance(task, dict):
        return False
    task_id = str(task.get("task_id") or "").strip()
    if plan is not None and task_id:
        completions = get_task_completions(plan)
        if task_id in completions:
            return bool(completions[task_id])
    return bool(task.get("completed"))


def set_task_completed(
    plan: dict[str, Any],
    task: dict[str, Any],
    completed: bool,
    *,
    course_scope: str | None,
) -> None:
    if not isinstance(plan, dict) or not isinstance(task, dict):
        return
    sync_quiz_required(task)
    task_id = build_task_id(task, course_scope)
    task["task_id"] = task_id
    task["completed"] = bool(completed)
    get_task_completions(plan)[task_id] = bool(completed)


def sync_completion_fields(plan: dict[str, Any], *, course_scope: str | None) -> None:
    """Keep task.completed and task_completions aligned (completion map is authoritative)."""
    if not isinstance(plan, dict):
        return
    completions = get_task_completions(plan)
    tasks = plan.get("tasks", [])
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if not isinstance(task, dict):
            continue
        sync_quiz_required(task)
        task_id = build_task_id(task, course_scope)
        task["task_id"] = task_id
        if task_id in completions:
            task["completed"] = bool(completions[task_id])
        elif bool(task.get("completed")):
            completions[task_id] = True
        else:
            completions.setdefault(task_id, False)


def ensure_task_ids(plan: dict[str, Any], course_scope: str | None) -> None:
    tasks = plan.get("tasks", [])
    if not isinstance(tasks, list):
        return
    for task in tasks:
        if not isinstance(task, dict):
            continue
        sync_quiz_required(task)
        task["task_id"] = build_task_id(task, course_scope)
    sync_completion_fields(plan, course_scope=course_scope)


def _parse_task_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _task_sort_key(task: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(task.get("date") or ""),
        str(task.get("phase") or ""),
        str(task.get("topic") or ""),
    )


def list_pending_tasks(
    plan: dict[str, Any] | None,
    course_scope: str | None,
    *,
    today_only: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(plan, dict):
        return []

    sync_completion_fields(plan, course_scope=course_scope)
    today = date.today()
    pending: list[dict[str, Any]] = []
    for task in plan.get("tasks", []) or []:
        if not isinstance(task, dict) or is_task_completed(task, plan):
            continue
        if today_only:
            task_date = _parse_task_date(task.get("date"))
            if task_date is None or task_date != today:
                continue
        pending.append(task)

    pending.sort(key=_task_sort_key)
    return pending


def select_next_task(
    plan: dict[str, Any] | None,
    course_scope: str | None,
    *,
    today_only: bool = False,
) -> dict[str, Any] | None:
    pending = list_pending_tasks(plan, course_scope, today_only=today_only)
    if not pending and today_only:
        pending = list_pending_tasks(plan, course_scope, today_only=False)
    return pending[0] if pending else None


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
    from src.tools.planner_localization import localize_study_task

    rows: list[dict[str, Any]] = []
    plan = {"tasks": tasks}
    sync_completion_fields(plan, course_scope=course_scope)
    for task in tasks:
        if not isinstance(task, dict):
            continue
        sync_quiz_required(task)
        task_id = build_task_id(task, course_scope)
        task["task_id"] = task_id
        localized_task = localize_study_task(task, language)
        rows.append(
            {
                "task_id": task_id,
                "date": task.get("date", ""),
                "topic": localized_task.get("topic", ""),
                "phase": localized_task.get("phase", ""),
                "task": localized_task.get("task", ""),
                "hours": task.get("hours", 0),
                "quiz_required_label": quiz_required_label(task, language),
                "mark_as_done": is_task_completed(task, plan),
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
        if is_task_completed(task, active_plan) != edited_completed:
            set_task_completed(active_plan, task, edited_completed, course_scope=course_scope)
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
        if not isinstance(task, dict) or not is_quiz_task(task) or is_task_completed(task, active_plan):
            continue
        if _topic_matches(str(task.get("topic") or ""), topic):
            candidates.append(task)

    if not candidates:
        for task in tasks:
            if not isinstance(task, dict) or not is_quiz_task(task) or is_task_completed(task, active_plan):
                continue
            candidates.append(task)

    if not candidates:
        return False

    def _sort_key(task: dict[str, Any]) -> tuple[int, str]:
        phase = str(task.get("phase") or "").casefold()
        priority = 0 if "checkpoint" in phase or task.get("checkpoint") else 1
        return priority, str(task.get("date") or "")

    target = sorted(candidates, key=_sort_key)[0]
    if is_task_completed(target, active_plan):
        return False
    set_task_completed(active_plan, target, True, course_scope=course_scope)
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
