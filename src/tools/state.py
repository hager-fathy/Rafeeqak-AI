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
from src.localization import normalize_language, t


COURSE_SCOPED_KEYS = (
    "chat_history",
    "chat_summaries",
    "study_plans",
    "active_plan",
    "quiz_attempts",
    "current_quiz",
    "last_quiz_feedback",
    "quiz_generation_status",
    "reminders",
    "uploads",
    "generated_questions",
)

WORKSPACE_VERSION = 1


def _empty_course_bucket() -> dict:
    return {
        "chat_history": [],
        "chat_summaries": [],
        "study_plans": [],
        "active_plan": None,
        "quiz_attempts": [],
        "current_quiz": None,
        "last_quiz_feedback": None,
        "quiz_generation_status": None,
        "reminders": [],
        "uploads": [],
        "generated_questions": [],
    }


def _normalize_course_bucket(bucket: dict | None) -> dict:
    normalized = _empty_course_bucket()
    if isinstance(bucket, dict):
        for key in COURSE_SCOPED_KEYS:
            value = bucket.get(key)
            if value is not None:
                normalized[key] = value
    return normalized


def init_state() -> None:
    defaults = {
        "chat_history": [],
        "chat_summaries": [],
        "study_plans": [],
        "active_plan": None,
        "quiz_attempts": [],
        "current_quiz": None,
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


def add_course(course_name: str, *, difficulty: str = "Medium") -> dict | None:
    normalized_name = " ".join(course_name.split())
    if not normalized_name:
        return None

    for course in st.session_state.get("courses", []):
        if course["name"].casefold() == normalized_name.casefold():
            set_active_course(course["id"])
            _save_user_workspace()
            return course

    course_id = _course_id(normalized_name)
    course = {
        "id": course_id,
        "name": normalized_name,
        "difficulty": difficulty,
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
        return

    bucket = get_active_course_bucket()
    for key in COURSE_SCOPED_KEYS:
        st.session_state[key] = bucket[key]


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
    return {
        "active_course": active_course,
        "active_course_id": active_course["id"] if active_course else None,
        "active_course_name": active_course["name"] if active_course else None,
        "active_plan": bucket.get("active_plan"),
        "study_plans": bucket.get("study_plans", []),
        "quiz_attempts": bucket.get("quiz_attempts", []),
        "quiz_generation_status": bucket.get("quiz_generation_status"),
        "reminders": bucket.get("reminders", []),
        "uploads": bucket.get("uploads", []),
        "chat_history": bucket.get("chat_history", []),
        "chat_summaries": bucket.get("chat_summaries", []),
        "generated_questions": bucket.get("generated_questions", []),
        "all_courses": _all_course_summaries(),
        "selected_language": get_selected_language(),
    }


def _migrate_legacy_course_state() -> None:
    if st.session_state.get("courses") or not any(st.session_state.get(key) for key in COURSE_SCOPED_KEYS):
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
        summaries.append(
            {
                "course_id": course["id"],
                "course_name": course["name"],
                "difficulty": course.get("difficulty", "Medium"),
                "plans": len(bucket.get("study_plans", []) or []),
                "total_tasks": len(tasks),
                "completed_tasks": sum(1 for task in tasks if task.get("completed")),
                "quiz_attempts": len(quiz_attempts),
                "average_score": average_score,
                "uploads": len(bucket.get("uploads", []) or []),
                "reminders": len(bucket.get("reminders", []) or []),
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
    load_user_workspace(user)


def clear_authenticated_user() -> None:
    _save_user_workspace()
    st.session_state["auth_user"] = None
    st.session_state["auth_access_token"] = None
    st.session_state["auth_refresh_token"] = None
    st.session_state["language_profile_loaded"] = False
    st.session_state["workspace_loaded_for"] = None


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

    for plan in bucket.get("study_plans", []) or []:
        if isinstance(plan, dict):
            plan["course_name"] = course_name

    active_plan = bucket.get("active_plan")
    if isinstance(active_plan, dict):
        active_plan["course_name"] = course_name

    current_quiz = bucket.get("current_quiz")
    if isinstance(current_quiz, dict):
        current_quiz["course_name"] = course_name


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
        st.session_state["selected_language"] = normalize_language(workspace.get("selected_language"))

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
        for key, value in _empty_course_bucket().items():
            st.session_state[key] = value
    finally:
        st.session_state["workspace_loading"] = False


def _workspace_path_for_email(email: str) -> Path:
    digest = hashlib.sha256(email.casefold().encode("utf-8")).hexdigest()[:24]
    return _workspace_store_dir() / f"{digest}.json"


def _workspace_store_dir() -> Path:
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
