import json
import hashlib
import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.agents.memory_agent import MemoryAgent
from src.agents.supervisor import SupervisorAgent
from src.auth.session_persistence import clear_persisted_tokens, persist_tokens
from src.config import load_project_env
from src.localization import normalize_language, t
from src.tools.quiz_history import QUIZ_HISTORY_VERSION


COURSE_SCOPED_KEYS = (
    "chat_history",
    "chat_summaries",
    "study_plans",
    "active_plan",
    "quiz_attempts",
    "active_quiz",
    "last_quiz_feedback",
    "quiz_generation_status",
    "reminders",
    "uploads",
    "generated_questions",
)

LEGACY_QUIZ_KEYS = ("current_quiz", "generated_quiz", "quiz")

WORKSPACE_VERSION = 1
VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_QUESTION_TYPES = {"mcq", "true_false", "short_answer", "matching"}
VALID_STUDY_PREFERENCES = {"balanced", "deep_focus", "practice_first", "exam_revision"}
VALID_REMINDER_TYPES = {"lecture", "revision", "quiz", "missed_task", "deadline", "study_task", "custom"}


def _empty_course_bucket() -> dict:
    return {
        "chat_history": [],
        "chat_summaries": [],
        "study_plans": [],
        "active_plan": None,
        "quiz_attempts": [],
        "active_quiz": None,
        "last_quiz_feedback": None,
        "quiz_generation_status": None,
        "reminders": [],
        "uploads": [],
        "generated_questions": {"version": QUIZ_HISTORY_VERSION, "scopes": {}},
    }


def _default_user_settings() -> dict:
    return {
        "full_name": "",
        "preferred_language": "en",
        "daily_study_hours": 2.0,
        "default_quiz_difficulty": "medium",
        "default_question_types": ["mcq"],
        "default_course_difficulty": "medium",
        "study_preference": "balanced",
        "reminder_preferences": {
            "enabled": True,
            "lead_days": 1,
            "reminder_time": "18:00",
            "types": ["lecture", "revision", "quiz", "missed_task", "deadline", "study_task", "custom"],
        },
    }


def _normalize_course_bucket(bucket: dict | None) -> dict:
    normalized = _empty_course_bucket()
    if isinstance(bucket, dict):
        for key in COURSE_SCOPED_KEYS:
            value = bucket.get(key)
            if value is not None:
                normalized[key] = value
        if normalized["active_quiz"] is None:
            for legacy_key in LEGACY_QUIZ_KEYS:
                legacy_quiz = bucket.get(legacy_key)
                if legacy_quiz is not None:
                    normalized["active_quiz"] = legacy_quiz
                    break
    return normalized


def _normalize_user_settings(settings: dict | None) -> dict:
    normalized = _default_user_settings()
    if not isinstance(settings, dict):
        return normalized

    full_name = str(settings.get("full_name") or "").strip()
    normalized["full_name"] = full_name[:120]
    normalized["preferred_language"] = normalize_language(settings.get("preferred_language"))
    normalized["daily_study_hours"] = _coerce_float(
        settings.get("daily_study_hours"),
        fallback=normalized["daily_study_hours"],
        minimum=0.5,
        maximum=12.0,
    )
    normalized["default_quiz_difficulty"] = _normalize_difficulty(
        settings.get("default_quiz_difficulty"),
        fallback=normalized["default_quiz_difficulty"],
    )
    normalized["default_question_types"] = _normalize_question_types(settings.get("default_question_types"))
    normalized["default_course_difficulty"] = _normalize_difficulty(
        settings.get("default_course_difficulty"),
        fallback=normalized["default_course_difficulty"],
    )
    normalized["study_preference"] = _normalize_choice(
        settings.get("study_preference"),
        valid=VALID_STUDY_PREFERENCES,
        fallback=normalized["study_preference"],
    )
    normalized["reminder_preferences"] = _normalize_reminder_preferences(settings.get("reminder_preferences"))
    return normalized


def init_state() -> None:
    defaults = {
        "chat_history": [],
        "chat_summaries": [],
        "study_plans": [],
        "active_plan": None,
        "quiz_attempts": [],
        "active_quiz": None,
        "last_quiz_feedback": None,
        "quiz_generation_status": None,
        "reminders": [],
        "uploads": [],
        "last_activity_at": datetime.utcnow().isoformat(timespec="seconds"),
        "memory_sync_notice": None,
        "auth_user": None,
        "auth_access_token": None,
        "auth_refresh_token": None,
        "courses": [],
        "active_course_id": None,
        "active_course_name": None,
        "course_data": {},
        "selected_language": "en",
        "user_settings": _default_user_settings(),
        "language_profile_loaded": False,
        "language_sync_notice": None,
        "workspace_loaded_for": None,
        "workspace_persistence_notice": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    _migrate_legacy_course_state()
    sync_active_course_aliases()


def touch_activity() -> None:
    st.session_state["last_activity_at"] = datetime.utcnow().isoformat(timespec="seconds")


def add_course(course_name: str, *, difficulty: str | None = None) -> dict | None:
    normalized_name = " ".join(course_name.split())
    if not normalized_name:
        return None

    for course in st.session_state.get("courses", []):
        if course["name"].casefold() == normalized_name.casefold():
            set_active_course(course["id"])
            _save_user_workspace()
            return course

    course_id = _course_id(normalized_name)
    course_difficulty = difficulty or get_user_settings().get("default_course_difficulty", "medium")
    course = {
        "id": course_id,
        "name": normalized_name,
        "difficulty": _normalize_difficulty(course_difficulty, fallback="medium").title(),
        "created_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
    }
    st.session_state["courses"].append(course)
    st.session_state["course_data"][course_id] = _empty_course_bucket()
    set_active_course(course_id)
    touch_activity()
    _save_user_workspace()
    return course


def get_courses() -> list[dict]:
    return st.session_state.get("courses", [])


def get_active_course() -> dict | None:
    active_course_id = st.session_state.get("active_course_id")
    for course in get_courses():
        if course["id"] == active_course_id:
            return course
    return None


def rename_course(course_id: str, course_name: str) -> dict:
    normalized_name = " ".join(course_name.split())
    if not normalized_name:
        return {"ok": False, "reason": "empty_name"}

    courses = get_courses()
    matching_course = next((course for course in courses if course["id"] == course_id), None)
    if matching_course is None:
        return {"ok": False, "reason": "missing_course"}

    duplicate = next(
        (
            course
            for course in courses
            if course["id"] != course_id and course["name"].casefold() == normalized_name.casefold()
        ),
        None,
    )
    if duplicate is not None:
        return {"ok": False, "reason": "duplicate_name"}

    matching_course["name"] = normalized_name
    _rename_course_references(course_id, normalized_name)
    if st.session_state.get("active_course_id") == course_id:
        st.session_state["active_course_name"] = normalized_name
        sync_active_course_aliases()
    touch_activity()
    _save_user_workspace()
    return {"ok": True, "course": matching_course}


def update_course_details(course_id: str, *, difficulty: str | None = None) -> dict:
    courses = get_courses()
    matching_course = next((course for course in courses if course["id"] == course_id), None)
    if matching_course is None:
        return {"ok": False, "reason": "missing_course"}

    if difficulty is not None:
        normalized_difficulty = str(difficulty).strip()
        if normalized_difficulty:
            matching_course["difficulty"] = normalized_difficulty

    touch_activity()
    _save_user_workspace()
    return {"ok": True, "course": matching_course}


def delete_course(course_id: str) -> dict:
    courses = get_courses()
    course = next((item for item in courses if item["id"] == course_id), None)
    if course is None:
        return {"ok": False, "reason": "missing_course"}

    st.session_state["courses"] = [item for item in courses if item["id"] != course_id]
    st.session_state.setdefault("course_data", {}).pop(course_id, None)

    if st.session_state.get("active_course_id") == course_id:
        next_course = st.session_state["courses"][0] if st.session_state["courses"] else None
        set_active_course(next_course["id"] if next_course else None)
    else:
        sync_active_course_aliases()

    touch_activity()
    _save_user_workspace()
    return {"ok": True, "course": course}


def set_active_course(course_id: str | None) -> None:
    course = next((item for item in get_courses() if item["id"] == course_id), None)
    if course is None:
        st.session_state["active_course_id"] = None
        st.session_state["active_course_name"] = None
        for key, value in _empty_course_bucket().items():
            st.session_state[key] = value
        _save_user_workspace()
        return

    st.session_state["active_course_id"] = course["id"]
    st.session_state["active_course_name"] = course["name"]
    st.session_state.setdefault("course_data", {}).setdefault(course["id"], _empty_course_bucket())
    sync_active_course_aliases()
    _save_user_workspace()


def require_active_course_message() -> str | None:
    if get_active_course() is None:
        return t("state.course_required", get_selected_language())
    return None


def get_selected_language() -> str:
    language = normalize_language(st.session_state.get("selected_language"))
    st.session_state["selected_language"] = language
    return language


def set_selected_language(language: str | None) -> bool:
    normalized = normalize_language(language)
    changed = normalized != st.session_state.get("selected_language")
    st.session_state["selected_language"] = normalized
    user_settings = get_user_settings()
    if user_settings.get("preferred_language") != normalized:
        user_settings["preferred_language"] = normalized
        st.session_state["user_settings"] = user_settings
    if changed:
        _save_user_workspace()
    return changed


def mark_language_profile_loaded() -> None:
    st.session_state["language_profile_loaded"] = True


def should_load_language_from_profile() -> bool:
    return not bool(st.session_state.get("language_profile_loaded"))


def get_active_course_bucket() -> dict:
    active_course = get_active_course()
    if active_course is None:
        return _empty_course_bucket()
    course_data = st.session_state.setdefault("course_data", {})
    bucket = _normalize_course_bucket(course_data.get(active_course["id"]))
    course_data[active_course["id"]] = bucket
    return bucket


def sync_active_course_aliases() -> None:
    active_course = get_active_course()
    if active_course is None:
        for key, value in _empty_course_bucket().items():
            st.session_state[key] = value
        _drop_legacy_quiz_aliases()
        return

    bucket = get_active_course_bucket()
    for key in COURSE_SCOPED_KEYS:
        st.session_state[key] = bucket[key]
    _drop_legacy_quiz_aliases()


def update_active_course_bucket(**values: object) -> None:
    active_course = get_active_course()
    if active_course is None:
        return

    bucket = get_active_course_bucket()
    for key, value in values.items():
        if key in COURSE_SCOPED_KEYS:
            bucket[key] = value
            st.session_state[key] = value
    _save_user_workspace()


def _drop_legacy_quiz_aliases() -> None:
    for key in LEGACY_QUIZ_KEYS:
        st.session_state.pop(key, None)


def get_user_settings() -> dict:
    settings = _normalize_user_settings(st.session_state.get("user_settings"))
    st.session_state["user_settings"] = settings
    return settings


def update_user_settings(settings: dict | None = None, **values: object) -> dict:
    current_settings = get_user_settings()
    merged = deepcopy(current_settings)
    updates = dict(settings or {})
    updates.update(values)

    for key, value in updates.items():
        if key == "reminder_preferences" and isinstance(value, dict):
            reminder_preferences = dict(merged.get("reminder_preferences", {}))
            reminder_preferences.update(value)
            merged["reminder_preferences"] = reminder_preferences
        else:
            merged[key] = value

    normalized = _normalize_user_settings(merged)
    st.session_state["user_settings"] = normalized
    st.session_state["selected_language"] = normalized["preferred_language"]
    touch_activity()
    _save_user_workspace()
    return normalized


def upsert_active_chat_summary(summary: dict, *, limit: int = 20) -> None:
    active_course = get_active_course()
    if active_course is None:
        return

    bucket = get_active_course_bucket()
    summaries = list(bucket.get("chat_summaries", []) or [])
    summary_id = summary.get("summary_id")
    if summary_id:
        summaries = [item for item in summaries if item.get("summary_id") != summary_id]
    summaries.append(summary)
    update_active_course_bucket(chat_summaries=summaries[-limit:])


def course_context() -> dict:
    active_course = get_active_course()
    bucket = get_active_course_bucket()
    user_settings = get_user_settings()
    return {
        "active_course": active_course,
        "active_course_id": active_course["id"] if active_course else None,
        "active_course_name": active_course["name"] if active_course else None,
        "active_plan": bucket.get("active_plan"),
        "study_plans": bucket.get("study_plans", []),
        "quiz_attempts": bucket.get("quiz_attempts", []),
        "active_quiz": bucket.get("active_quiz"),
        "last_quiz_feedback": bucket.get("last_quiz_feedback"),
        "quiz_generation_status": bucket.get("quiz_generation_status"),
        "reminders": bucket.get("reminders", []),
        "uploads": bucket.get("uploads", []),
        "chat_history": bucket.get("chat_history", []),
        "chat_summaries": bucket.get("chat_summaries", []),
        "generated_questions": bucket.get("generated_questions", []),
        "all_courses": _all_course_summaries(),
        "selected_language": get_selected_language(),
        "user_settings": user_settings,
        "quiz_difficulty": user_settings["default_quiz_difficulty"],
        "question_types": user_settings["default_question_types"],
        "reminder_preferences": user_settings["reminder_preferences"],
    }


def _migrate_legacy_course_state() -> None:
    legacy_keys = COURSE_SCOPED_KEYS + LEGACY_QUIZ_KEYS
    if st.session_state.get("courses") or not any(st.session_state.get(key) for key in legacy_keys):
        return

    course_name = "General Studies"
    active_plan = st.session_state.get("active_plan")
    if isinstance(active_plan, dict) and active_plan.get("course_name"):
        course_name = active_plan["course_name"]

    course_id = _course_id(course_name)
    st.session_state["courses"] = [
        {
            "id": course_id,
            "name": course_name,
            "difficulty": "Medium",
            "created_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
        }
    ]
    st.session_state["active_course_id"] = course_id
    st.session_state["active_course_name"] = course_name
    st.session_state["course_data"] = {
        course_id: {
            key: deepcopy(st.session_state.get(key, _empty_course_bucket()[key]))
            for key in COURSE_SCOPED_KEYS
        }
    }
    if st.session_state["course_data"][course_id]["active_quiz"] is None:
        for legacy_key in LEGACY_QUIZ_KEYS:
            legacy_quiz = st.session_state.get(legacy_key)
            if legacy_quiz is not None:
                st.session_state["course_data"][course_id]["active_quiz"] = deepcopy(legacy_quiz)
                break


def _course_id(course_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", course_name.lower()).strip("-") or "course"
    digest = hashlib.sha1(course_name.casefold().encode("utf-8")).hexdigest()[:8]
    return f"{slug}-{digest}"


def _all_course_summaries() -> list[dict]:
    summaries = []
    course_data = st.session_state.get("course_data", {})
    for course in get_courses():
        bucket = course_data.get(course["id"], _empty_course_bucket())
        active_plan = bucket.get("active_plan") or {}
        tasks = active_plan.get("tasks", []) if isinstance(active_plan, dict) else []
        completed_tasks = [task for task in tasks if isinstance(task, dict) and task.get("completed")]
        upcoming_tasks = [
            task
            for task in tasks
            if isinstance(task, dict) and not task.get("completed") and str(task.get("date", "")).strip()
        ]
        upcoming_tasks = sorted(upcoming_tasks, key=lambda task: str(task.get("date") or ""))
        next_task = upcoming_tasks[0] if upcoming_tasks else None
        quiz_attempts = bucket.get("quiz_attempts", []) or []
        average_score = 0.0
        if quiz_attempts:
            average_score = round(
                sum(item.get("score_percent", 0) for item in quiz_attempts) / len(quiz_attempts),
                1,
            )
        weak_topics = set(active_plan.get("weak_topics", []) if isinstance(active_plan, dict) else [])
        for attempt in quiz_attempts:
            weak_topics.update(attempt.get("weak_topics", []) or [])
        reminders = [item for item in bucket.get("reminders", []) or [] if isinstance(item, dict)]
        pending_reminders = [item for item in reminders if item.get("status") != "done"]
        completion_rate = round((len(completed_tasks) / len(tasks)) * 100, 1) if tasks else 0.0
        summaries.append(
            {
                "course_id": course["id"],
                "course_name": course["name"],
                "difficulty": course.get("difficulty", "Medium"),
                "plans": len(bucket.get("study_plans", []) or []),
                "total_tasks": len(tasks),
                "completed_tasks": len(completed_tasks),
                "completion_rate": completion_rate,
                "upcoming_tasks": len(upcoming_tasks),
                "next_task": next_task,
                "quiz_attempts": len(quiz_attempts),
                "average_score": average_score,
                "uploads": len(bucket.get("uploads", []) or []),
                "reminders": len(reminders),
                "pending_reminders": len(pending_reminders),
                "next_reminder": sorted(pending_reminders, key=lambda item: item.get("due_at") or "")[0]
                if pending_reminders
                else None,
                "chat_summaries": len(bucket.get("chat_summaries", []) or []),
                "weak_topics": sorted(weak_topics),
                "exam_date": active_plan.get("exam_date") if isinstance(active_plan, dict) else None,
            }
        )
    return summaries


def get_memory_agent() -> MemoryAgent:
    if "memory_agent" not in st.session_state:
        st.session_state["memory_agent"] = MemoryAgent()
    return st.session_state["memory_agent"]


def get_supervisor_agent() -> SupervisorAgent:
    if "supervisor_agent" not in st.session_state:
        st.session_state["supervisor_agent"] = SupervisorAgent()
    return st.session_state["supervisor_agent"]


def set_authenticated_user(
    *,
    user: dict,
    access_token: str | None,
    refresh_token: str | None,
) -> None:
    st.session_state["auth_user"] = user
    st.session_state["auth_access_token"] = access_token
    st.session_state["auth_refresh_token"] = refresh_token
    persist_tokens(access_token, refresh_token)
    load_user_workspace(user)


def clear_authenticated_user() -> None:
    _save_user_workspace()
    st.session_state["auth_user"] = None
    st.session_state["auth_access_token"] = None
    st.session_state["auth_refresh_token"] = None
    st.session_state["language_profile_loaded"] = False
    st.session_state["workspace_loaded_for"] = None
    clear_persisted_tokens()


def get_authenticated_user() -> dict | None:
    return st.session_state.get("auth_user")


def is_authenticated() -> bool:
    return st.session_state.get("auth_user") is not None


def load_user_workspace(user: dict | None = None) -> dict:
    email = _user_email(user or get_authenticated_user())
    if not email:
        return {"ok": False, "reason": "missing_email"}
    if st.session_state.get("workspace_loaded_for") == email:
        return {"ok": True, "loaded": False, "reason": "already_loaded"}

    workspace_path = _workspace_path_for_email(email)
    if not workspace_path.exists():
        _reset_workspace_state()
        st.session_state["workspace_loaded_for"] = email
        st.session_state["workspace_persistence_notice"] = "empty"
        return {"ok": True, "loaded": False, "reason": "not_found"}

    try:
        payload = json.loads(workspace_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        _reset_workspace_state()
        st.session_state["workspace_loaded_for"] = email
        st.session_state["workspace_persistence_notice"] = f"load_failed:{exc}"
        return {"ok": False, "loaded": False, "reason": str(exc)}

    workspace = payload.get("workspace", {}) if isinstance(payload, dict) else {}
    if not isinstance(workspace, dict):
        _reset_workspace_state()
        st.session_state["workspace_loaded_for"] = email
        st.session_state["workspace_persistence_notice"] = "invalid"
        return {"ok": False, "loaded": False, "reason": "invalid_workspace"}

    _apply_workspace_state(workspace)
    st.session_state["workspace_loaded_for"] = email
    st.session_state["workspace_persistence_notice"] = "loaded"
    return {"ok": True, "loaded": True, "path": str(workspace_path)}


def _rename_course_references(course_id: str, course_name: str) -> None:
    bucket = st.session_state.setdefault("course_data", {}).setdefault(course_id, _empty_course_bucket())
    for item in bucket.get("uploads", []) or []:
        item["course_name"] = course_name
    for item in bucket.get("quiz_attempts", []) or []:
        item["course_name"] = course_name
    for item in bucket.get("reminders", []) or []:
        item["course_name"] = course_name

    for plan in bucket.get("study_plans", []) or []:
        if isinstance(plan, dict):
            plan["course_name"] = course_name

    active_plan = bucket.get("active_plan")
    if isinstance(active_plan, dict):
        active_plan["course_name"] = course_name

    active_quiz = bucket.get("active_quiz")
    if isinstance(active_quiz, dict):
        active_quiz["course_name"] = course_name


def _save_user_workspace() -> dict:
    if st.session_state.get("workspace_loading"):
        return {"ok": False, "reason": "loading"}

    user = get_authenticated_user()
    email = _user_email(user)
    if not email:
        return {"ok": False, "reason": "missing_email"}

    workspace_path = _workspace_path_for_email(email)
    payload = {
        "version": WORKSPACE_VERSION,
        "email": email,
        "updated_at_utc": datetime.utcnow().isoformat(timespec="seconds"),
        "workspace": _current_workspace_state(),
    }
    try:
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        workspace_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        st.session_state["workspace_persistence_notice"] = f"save_failed:{exc}"
        return {"ok": False, "reason": str(exc)}

    st.session_state["workspace_loaded_for"] = email
    st.session_state["workspace_persistence_notice"] = "saved"
    return {"ok": True, "path": str(workspace_path)}


def _current_workspace_state() -> dict:
    course_data = st.session_state.get("course_data", {})
    normalized_course_data = {}
    if isinstance(course_data, dict):
        for course_id, bucket in course_data.items():
            normalized_course_data[str(course_id)] = _normalize_course_bucket(bucket)

    return {
        "courses": deepcopy(st.session_state.get("courses", [])),
        "active_course_id": st.session_state.get("active_course_id"),
        "active_course_name": st.session_state.get("active_course_name"),
        "course_data": normalized_course_data,
        "selected_language": get_selected_language(),
        "user_settings": deepcopy(get_user_settings()),
    }


def _apply_workspace_state(workspace: dict) -> None:
    st.session_state["workspace_loading"] = True
    try:
        courses = workspace.get("courses", [])
        st.session_state["courses"] = courses if isinstance(courses, list) else []

        raw_course_data = workspace.get("course_data", {})
        course_data = {}
        if isinstance(raw_course_data, dict):
            for course_id, bucket in raw_course_data.items():
                course_data[str(course_id)] = _normalize_course_bucket(bucket)
        st.session_state["course_data"] = course_data

        st.session_state["active_course_id"] = workspace.get("active_course_id")
        st.session_state["active_course_name"] = workspace.get("active_course_name")
        st.session_state["user_settings"] = _normalize_user_settings(workspace.get("user_settings"))
        st.session_state["selected_language"] = normalize_language(
            workspace.get("selected_language") or st.session_state["user_settings"].get("preferred_language")
        )
        st.session_state["user_settings"]["preferred_language"] = st.session_state["selected_language"]

        if get_active_course() is None:
            next_course = st.session_state["courses"][0] if st.session_state["courses"] else None
            st.session_state["active_course_id"] = next_course["id"] if next_course else None
            st.session_state["active_course_name"] = next_course["name"] if next_course else None
        sync_active_course_aliases()
    finally:
        st.session_state["workspace_loading"] = False


def _reset_workspace_state() -> None:
    st.session_state["workspace_loading"] = True
    try:
        st.session_state["courses"] = []
        st.session_state["active_course_id"] = None
        st.session_state["active_course_name"] = None
        st.session_state["course_data"] = {}
        st.session_state["selected_language"] = "en"
        st.session_state["user_settings"] = _default_user_settings()
        for key, value in _empty_course_bucket().items():
            st.session_state[key] = value
    finally:
        st.session_state["workspace_loading"] = False


def _workspace_path_for_email(email: str) -> Path:
    digest = hashlib.sha256(email.casefold().encode("utf-8")).hexdigest()[:24]
    return _workspace_store_dir() / f"{digest}.json"


def _workspace_store_dir() -> Path:
    load_project_env()
    configured = os.getenv("RAFEEQAK_USER_STATE_DIR")
    if configured:
        return Path(configured)
    return Path("data") / "user_state"


def _user_email(user: dict | None) -> str | None:
    if not isinstance(user, dict):
        return None
    email = user.get("email")
    if not email:
        return None
    return str(email).strip().casefold() or None


def _normalize_difficulty(value: object, *, fallback: str) -> str:
    return _normalize_choice(value, valid=VALID_DIFFICULTIES, fallback=fallback)


def _normalize_choice(value: object, *, valid: set[str], fallback: str) -> str:
    normalized = str(value or fallback).strip().lower()
    return normalized if normalized in valid else fallback


def _normalize_question_types(value: object) -> list[str]:
    raw_values = value if isinstance(value, list) else []
    normalized = []
    for item in raw_values:
        question_type = str(item).strip().lower()
        if question_type in VALID_QUESTION_TYPES and question_type not in normalized:
            normalized.append(question_type)
    return normalized or ["mcq"]


def _normalize_reminder_preferences(value: object) -> dict:
    defaults = _default_user_settings()["reminder_preferences"]
    preferences = value if isinstance(value, dict) else {}
    try:
        lead_days = int(preferences.get("lead_days", defaults["lead_days"]))
    except (TypeError, ValueError):
        lead_days = defaults["lead_days"]
    lead_days = min(max(lead_days, 0), 14)

    reminder_time = str(preferences.get("reminder_time") or defaults["reminder_time"]).strip()
    if not re.match(r"^\d{2}:\d{2}$", reminder_time):
        reminder_time = defaults["reminder_time"]

    raw_types = preferences.get("types")
    if not isinstance(raw_types, list):
        raw_types = defaults["types"]
    reminder_types = []
    for item in raw_types:
        reminder_type = str(item).strip().lower()
        if reminder_type in VALID_REMINDER_TYPES and reminder_type not in reminder_types:
            reminder_types.append(reminder_type)

    return {
        "enabled": bool(preferences.get("enabled", defaults["enabled"])),
        "lead_days": lead_days,
        "reminder_time": reminder_time,
        "types": reminder_types or list(defaults["types"]),
    }


def _coerce_float(value: object, *, fallback: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = fallback
    return round(min(max(parsed, minimum), maximum), 1)
