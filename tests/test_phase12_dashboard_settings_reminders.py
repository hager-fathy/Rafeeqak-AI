from datetime import date, datetime, timedelta

import streamlit as st

from src.agents.reminder_agent import ReminderAgent
from src.tools.state import (
    add_course,
    course_context,
    get_user_settings,
    init_state,
    set_authenticated_user,
    update_user_settings,
)
from src.ui.dashboard_page import build_dashboard_course_rows, due_reminder_rows


def setup_function() -> None:
    st.session_state.clear()


def test_user_settings_persist_and_drive_defaults(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("RAFEEQAK_USER_STATE_DIR", str(tmp_path / "user_state"))
    user = {"email": "student@example.com", "user_metadata": {"full_name": "Demo Student"}}

    init_state()
    set_authenticated_user(user=user, access_token="access", refresh_token="refresh")
    saved = update_user_settings(
        {
            "full_name": "Security Student",
            "preferred_language": "en",
            "daily_study_hours": 3.5,
            "default_course_difficulty": "hard",
            "default_quiz_difficulty": "hard",
            "default_question_types": ["mcq", "short_answer"],
            "study_preference": "practice_first",
            "reminder_preferences": {
                "enabled": True,
                "lead_days": 2,
                "reminder_time": "20:30",
                "types": ["lecture", "quiz", "deadline"],
            },
        }
    )
    course = add_course("Cybersecurity")

    assert saved["daily_study_hours"] == 3.5
    assert course["difficulty"] == "Hard"
    assert course_context()["quiz_difficulty"] == "hard"
    assert course_context()["question_types"] == ["mcq", "short_answer"]

    st.session_state.clear()
    init_state()
    set_authenticated_user(user=user, access_token="access", refresh_token="refresh")

    restored = get_user_settings()
    assert restored["full_name"] == "Security Student"
    assert restored["daily_study_hours"] == 3.5
    assert restored["reminder_preferences"]["reminder_time"] == "20:30"
    assert restored["default_course_difficulty"] == "hard"


def test_reminder_agent_creates_phase12_reminder_types() -> None:
    today = date.today()
    plan = {
        "course_name": "Networks",
        "exam_date": (today + timedelta(days=6)).isoformat(),
        "weak_topics": ["Subnetting"],
        "tasks": [
            {
                "date": (today - timedelta(days=1)).isoformat(),
                "topic": "Routing",
                "phase": "Concept review",
                "task": "Review routing tables.",
                "checkpoint": False,
                "completed": False,
            },
            {
                "date": today.isoformat(),
                "topic": "Lecture 1",
                "phase": "Concept review",
                "task": "Cover Lecture 1 first.",
                "checkpoint": False,
                "completed": False,
            },
            {
                "date": (today + timedelta(days=1)).isoformat(),
                "topic": "Subnetting",
                "phase": "Final review",
                "task": "Do final review and practice.",
                "checkpoint": True,
                "completed": False,
            },
        ],
    }

    result = ReminderAgent().create(
        message="create reminders",
        context={
            "active_course_id": "net-1",
            "active_course_name": "Networks",
            "active_plan": plan,
            "quiz_attempts": [],
            "reminders": [],
            "reminder_preferences": {
                "enabled": True,
                "lead_days": 1,
                "reminder_time": "19:15",
                "types": ["lecture", "revision", "quiz", "missed_task", "deadline", "study_task", "custom"],
            },
        },
    )

    reminder_types = {item["reminder_type"] for item in result["reminders"]}

    assert result["ok"] is True
    assert {"lecture", "revision", "quiz", "missed_task", "deadline"} <= reminder_types
    assert all(item["course_id"] == "net-1" for item in result["reminders"])
    assert any(item["due_at"].endswith("19:15") for item in result["reminders"])


def test_reminder_agent_respects_disabled_preference() -> None:
    result = ReminderAgent().create(
        message="Remind me to revise tomorrow",
        context={
            "active_course_id": "ml-1",
            "active_course_name": "Machine Learning",
            "active_plan": {},
            "reminders": [],
            "reminder_preferences": {"enabled": False},
        },
    )

    assert result["status"] == "disabled"
    assert result["created_count"] == 0
    assert result["reminders"] == []


def test_dashboard_course_rows_and_due_reminders() -> None:
    rows = build_dashboard_course_rows(
        [
            {
                "course_name": "Databases",
                "difficulty": "Hard",
                "completion_rate": 50.0,
                "completed_tasks": 2,
                "total_tasks": 4,
                "upcoming_tasks": 2,
                "next_task": {"topic": "Indexes", "date": "2026-05-17"},
                "quiz_attempts": 1,
                "average_score": 72.5,
                "weak_topics": ["Transactions"],
                "uploads": 3,
                "exam_date": "2026-06-01",
                "pending_reminders": 2,
                "next_reminder": {"title": "Study Indexes", "due_at": "2026-05-16T18:00"},
            }
        ]
    )

    assert rows[0]["course"] == "Databases"
    assert rows[0]["progress_percent"] == 50.0
    assert rows[0]["next_task"] == "Indexes"
    assert rows[0]["weak_topics"] == "Transactions"

    now = datetime(2026, 5, 16, 12, 0)
    due_rows = due_reminder_rows(
        [
            {"title": "Due", "due_at": "2026-05-16T18:00", "status": "pending"},
            {"title": "Later", "due_at": "2026-05-20T18:00", "status": "pending"},
            {"title": "Done", "due_at": "2026-05-16T10:00", "status": "done"},
        ],
        now=now,
    )

    assert [item["title"] for item in due_rows] == ["Due"]
