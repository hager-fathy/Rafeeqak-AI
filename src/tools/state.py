import hashlib
import re
from copy import deepcopy
from datetime import datetime

import streamlit as st

from src.agents.memory_agent import MemoryAgent
from src.agents.supervisor import SupervisorAgent
from src.localization import normalize_language, t


COURSE_SCOPED_KEYS = (
    "chat_history",
    "study_plans",
    "active_plan",
    "quiz_attempts",
    "current_quiz",
    "last_quiz_feedback",
    "uploads",
    "generated_questions",
)


def _empty_course_bucket() -> dict:
    return {
        "chat_history": [],
        "study_plans": [],
        "active_plan": None,
        "quiz_attempts": [],
        "current_quiz": None,
        "last_quiz_feedback": None,
        "uploads": [],
        "generated_questions": [],
    }


def init_state() -> None:
    defaults = {
        "chat_history": [],
        "study_plans": [],
        "active_plan": None,
        "quiz_attempts": [],
        "current_quiz": None,
        "last_quiz_feedback": None,
        "uploads": [],
        "last_activity_at": datetime.utcnow().isoformat(timespec="seconds"),
        "memory_sync_notice": None,
        "route_traces": [],
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
    return course


def get_courses() -> list[dict]:
    return st.session_state.get("courses", [])


def get_active_course() -> dict | None:
    active_course_id = st.session_state.get("active_course_id")
    for course in get_courses():
        if course["id"] == active_course_id:
            return course
    return None


def set_active_course(course_id: str | None) -> None:
    course = next((item for item in get_courses() if item["id"] == course_id), None)
    if course is None:
        st.session_state["active_course_id"] = None
        st.session_state["active_course_name"] = None
        sync_active_course_aliases()
        return

    st.session_state["active_course_id"] = course["id"]
    st.session_state["active_course_name"] = course["name"]
    st.session_state.setdefault("course_data", {}).setdefault(course["id"], _empty_course_bucket())
    sync_active_course_aliases()


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
    return changed


def mark_language_profile_loaded() -> None:
    st.session_state["language_profile_loaded"] = True


def should_load_language_from_profile() -> bool:
    return not bool(st.session_state.get("language_profile_loaded"))


def get_active_course_bucket() -> dict:
    active_course = get_active_course()
    if active_course is None:
        return _empty_course_bucket()
    return st.session_state.setdefault("course_data", {}).setdefault(active_course["id"], _empty_course_bucket())


def sync_active_course_aliases() -> None:
    active_course = get_active_course()
    if active_course is None:
        return

    bucket = get_active_course_bucket()
    for key in COURSE_SCOPED_KEYS:
        st.session_state[key] = bucket.get(key)


def update_active_course_bucket(**values: object) -> None:
    active_course = get_active_course()
    if active_course is None:
        return

    bucket = get_active_course_bucket()
    for key, value in values.items():
        if key in COURSE_SCOPED_KEYS:
            bucket[key] = value
            st.session_state[key] = value


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
        "uploads": bucket.get("uploads", []),
        "chat_history": bucket.get("chat_history", []),
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


def append_route_trace(trace: list[dict]) -> None:
    if "route_traces" not in st.session_state:
        st.session_state["route_traces"] = []
    st.session_state["route_traces"].append(trace)
    st.session_state["route_traces"] = st.session_state["route_traces"][-20:]


def set_authenticated_user(
    *,
    user: dict,
    access_token: str | None,
    refresh_token: str | None,
) -> None:
    st.session_state["auth_user"] = user
    st.session_state["auth_access_token"] = access_token
    st.session_state["auth_refresh_token"] = refresh_token


def clear_authenticated_user() -> None:
    st.session_state["auth_user"] = None
    st.session_state["auth_access_token"] = None
    st.session_state["auth_refresh_token"] = None
    st.session_state["language_profile_loaded"] = False


def get_authenticated_user() -> dict | None:
    return st.session_state.get("auth_user")


def is_authenticated() -> bool:
    return st.session_state.get("auth_user") is not None
