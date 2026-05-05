from datetime import datetime

import streamlit as st

from src.agents.memory_agent import MemoryAgent
from src.agents.supervisor import SupervisorAgent


def init_state() -> None:
    defaults = {
        "chat_history": [],
        "study_plans": [],
        "active_plan": None,
        "quiz_attempts": [],
        "current_quiz": None,
        "uploads": [],
        "last_activity_at": datetime.utcnow().isoformat(timespec="seconds"),
        "memory_sync_notice": None,
        "route_traces": [],
        "auth_user": None,
        "auth_access_token": None,
        "auth_refresh_token": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def touch_activity() -> None:
    st.session_state["last_activity_at"] = datetime.utcnow().isoformat(timespec="seconds")


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


def get_authenticated_user() -> dict | None:
    return st.session_state.get("auth_user")


def is_authenticated() -> bool:
    return st.session_state.get("auth_user") is not None
