from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.agents.reminder_agent import ReminderAgent
from src.localization import t
from src.retrieval import CourseMaterialIndexer
from src.tools.semantic_cache import SemanticResponseCache
from src.tools.study_plan_tasks import is_task_completed
from src.tools.state import (
    course_context,
    get_active_course,
    get_authenticated_user,
    get_memory_agent,
    get_selected_language,
    touch_activity,
    update_active_course_bucket,
)
from src.ui.theme import render_page_hero


def render_dashboard_page(project_root: Path) -> None:
    language = get_selected_language()
    active_course = get_active_course()
    current_context = course_context()
    all_courses = current_context.get("all_courses", [])
    study_plans = current_context.get("study_plans", [])
    quiz_attempts = current_context.get("quiz_attempts", [])
    uploads = current_context.get("uploads", [])
    chat_summaries = current_context.get("chat_summaries", [])
    reminders = current_context.get("reminders", [])
    indexer = CourseMaterialIndexer(
        uploads_dir=project_root / "data" / "uploads",
        vector_store_dir=project_root / "data" / "vector_store",
    )
    retrieval_stats = indexer.stats(course_id=active_course["id"] if active_course else None)
    cache_stats = SemanticResponseCache().stats()
    memory_agent = get_memory_agent()
    memory_status = memory_agent.status()
    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None

    average_quiz = _average_score(quiz_attempts)
    overall = _overall_metrics(all_courses)

    render_page_hero(
        t("dashboard.title", language),
        t("dashboard.subtitle", language),
        chips=[
            f"{t('planner.course_name', language)}: {active_course['name'] if active_course else t('course.none_selected', language)}",
            t("dashboard.plans_chip", language, count=len(study_plans)),
            t("dashboard.uploads_chip", language, count=len(uploads)),
            t("quiz.rag_chip", language, count=retrieval_stats["chunks"]),
            t("dashboard.cache_chip", language, count=cache_stats["entries"]),
            t("dashboard.quiz_avg_chip", language, score=average_quiz),
            f"{t('dashboard.chat_summaries', language)}: {len(chat_summaries)}",
            f"{t('dashboard.reminders', language)}: {len(reminders)}",
        ],
        accent_chip=t("dashboard.accent", language),
        language=language,
    )

    metric_cols = st.columns(6)
    metric_cols[0].metric(t("dashboard.all_courses", language), overall["courses"], border=True)
    metric_cols[1].metric(t("dashboard.completed_tasks", language), overall["completed_tasks"], border=True)
    metric_cols[2].metric(t("dashboard.upcoming_tasks", language), overall["upcoming_tasks"], border=True)
    metric_cols[3].metric(t("dashboard.average_score", language), f"{overall['average_score']}%", border=True)
    metric_cols[4].metric(t("dashboard.uploads", language), overall["uploads"], border=True)
    metric_cols[5].metric(t("dashboard.reminders", language), overall["pending_reminders"], border=True)

    st.caption(
        t("dashboard.memory_connected", language)
        if memory_status["enabled"]
        else t("dashboard.memory_status", language, reason=memory_status["reason"])
    )

    _render_course_overview(all_courses, language)
    _render_active_course_panels(current_context, language)
    _render_reminder_panel(
        current_context=current_context,
        memory_agent=memory_agent,
        student_email=student_email,
        student_name=student_name,
        language=language,
    )
    _render_quiz_trend(quiz_attempts, language)
    _render_plan_overview(current_context, language)
    _render_chat_summary(chat_summaries, language)
    _render_memory_snapshot(memory_agent, memory_status, student_email, student_name, language)


def build_dashboard_course_rows(course_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for course in course_summaries:
        next_task = course.get("next_task") if isinstance(course.get("next_task"), dict) else {}
        next_reminder = course.get("next_reminder") if isinstance(course.get("next_reminder"), dict) else {}
        rows.append(
            {
                "course": course.get("course_name"),
                "difficulty": course.get("difficulty"),
                "progress_percent": course.get("completion_rate", 0.0),
                "completed_tasks": course.get("completed_tasks", 0),
                "total_tasks": course.get("total_tasks", 0),
                "upcoming_tasks": course.get("upcoming_tasks", 0),
                "next_task": next_task.get("topic"),
                "next_task_date": next_task.get("date"),
                "quiz_attempts": course.get("quiz_attempts", 0),
                "average_score": course.get("average_score", 0.0),
                "weak_topics": ", ".join(course.get("weak_topics", [])[:4]),
                "uploads": course.get("uploads", 0),
                "deadline": course.get("exam_date"),
                "pending_reminders": course.get("pending_reminders", 0),
                "next_reminder": next_reminder.get("title"),
                "next_reminder_due": next_reminder.get("due_at"),
            }
        )
    return rows


def due_reminder_rows(reminders: list[dict[str, Any]], *, now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now()
    due_soon = now + timedelta(days=1)
    rows = []
    for reminder in reminders:
        if not isinstance(reminder, dict) or reminder.get("status") == "done":
            continue
        due_at = _parse_datetime(reminder.get("due_at"))
        if due_at is None or due_at > due_soon:
            continue
        rows.append({**reminder, "due_datetime": due_at})
    return sorted(rows, key=lambda item: item["due_datetime"])


def _render_course_overview(all_courses: list[dict[str, Any]], language: str) -> None:
    st.markdown(f"### {t('dashboard.all_courses', language)}")
    if not all_courses:
        st.info(t("dashboard.no_courses", language))
        return

    rows = build_dashboard_course_rows(all_courses)
    card_cols = st.columns(3)
    for index, course in enumerate(all_courses):
        with card_cols[index % 3].container(border=True):
            st.markdown(f"#### {course['course_name']}")
            progress = float(course.get("completion_rate") or 0.0)
            st.progress(min(max(progress / 100.0, 0.0), 1.0))
            st.caption(
                t(
                    "dashboard.course_progress",
                    language,
                    completed=course.get("completed_tasks", 0),
                    total=course.get("total_tasks", 0),
                    percent=progress,
                )
            )
            next_task = course.get("next_task") if isinstance(course.get("next_task"), dict) else None
            if next_task:
                st.caption(t("dashboard.next_task", language, topic=next_task.get("topic"), date=next_task.get("date")))
            else:
                st.caption(t("dashboard.no_next_task", language))
            st.caption(
                t("dashboard.deadline", language, date=course.get("exam_date"))
                if course.get("exam_date")
                else t("dashboard.no_deadline", language)
            )
            weak_topics = course.get("weak_topics", [])
            st.caption(
                t("dashboard.weak_topics_inline", language, topics=", ".join(weak_topics[:4]))
                if weak_topics
                else t("dashboard.no_weak_topics_inline", language)
            )
            st.metric(t("dashboard.average_score", language), f"{course.get('average_score', 0.0)}%", border=True)
            st.caption(t("dashboard.pending_reminders", language, count=course.get("pending_reminders", 0)))

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_active_course_panels(current_context: dict[str, Any], language: str) -> None:
    active_plan = current_context.get("active_plan") or {}
    tasks = active_plan.get("tasks", []) if isinstance(active_plan, dict) else []
    completed_tasks = [task for task in tasks if isinstance(task, dict) and is_task_completed(task, active_plan)]
    upcoming_tasks = [task for task in tasks if isinstance(task, dict) and not is_task_completed(task, active_plan)]
    deadline = active_plan.get("exam_date") if isinstance(active_plan, dict) else None

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric(t("dashboard.plans_created", language), len(current_context.get("study_plans", [])), border=True)
    col2.metric(t("dashboard.completed_tasks", language), len(completed_tasks), border=True)
    col3.metric(t("dashboard.upcoming_tasks", language), len(upcoming_tasks), border=True)
    col4.metric(t("dashboard.quiz_attempts", language), len(current_context.get("quiz_attempts", [])), border=True)
    col5.metric(t("dashboard.uploaded_files", language), len(current_context.get("uploads", [])), border=True)
    col6.metric(t("dashboard.deadlines", language), deadline or t("dashboard.no_deadline", language), border=True)

    task_cols = st.columns(2, gap="large")
    with task_cols[0]:
        st.markdown(f"#### {t('dashboard.completed_tasks', language)}")
        _render_task_table(completed_tasks[-8:], language)
    with task_cols[1]:
        st.markdown(f"#### {t('dashboard.upcoming_tasks', language)}")
        _render_task_table(upcoming_tasks[:8], language)


def _render_task_table(tasks: list[dict[str, Any]], language: str) -> None:
    if not tasks:
        st.info(t("dashboard.no_next_task", language))
        return
    columns = [column for column in ["date", "topic", "phase", "hours", "checkpoint"] if column in tasks[0]]
    st.dataframe(pd.DataFrame(tasks)[columns], use_container_width=True, hide_index=True)


def _render_reminder_panel(
    *,
    current_context: dict[str, Any],
    memory_agent: Any,
    student_email: str | None,
    student_name: str | None,
    language: str,
) -> None:
    st.markdown(f"### {t('dashboard.upcoming_reminders', language)}")
    refresh_col, _ = st.columns([1, 3])
    with refresh_col:
        if st.button(
            t("dashboard.refresh_reminders", language),
            use_container_width=True,
            disabled=current_context.get("active_course_id") is None,
        ):
            result = ReminderAgent().create(
                message="create reminders for this course",
                context=current_context,
                language=language,
            )
            update_active_course_bucket(reminders=result["reminders"])
            touch_activity()
            st.success(t("dashboard.reminders_refreshed", language, count=result["created_count"]))
            _sync_reminders(
                reminders=result["reminders"],
                course_name=current_context.get("active_course_name"),
                memory_agent=memory_agent,
                student_email=student_email,
                student_name=student_name,
                language=language,
            )

    reminders = course_context().get("reminders", [])
    pending_reminders = [item for item in reminders if isinstance(item, dict) and item.get("status") != "done"]
    due_rows = due_reminder_rows(pending_reminders)
    if due_rows:
        st.markdown(f"#### {t('dashboard.notifications', language)}")
        for reminder in due_rows[:5]:
            st.warning(
                t(
                    "dashboard.notification_due",
                    language,
                    course=reminder.get("course_name") or current_context.get("active_course_name"),
                    title=reminder.get("title"),
                    due_at=reminder.get("due_at"),
                )
            )
    else:
        st.caption(t("dashboard.no_notifications", language))

    if not pending_reminders:
        st.info(t("dashboard.no_reminders", language))
        return

    reminder_df = pd.DataFrame(pending_reminders)
    visible_columns = [
        column
        for column in ["title", "reminder_type", "due_at", "status", "source", "course_name"]
        if column in reminder_df.columns
    ]
    st.dataframe(reminder_df[visible_columns], use_container_width=True, hide_index=True)

    for reminder in pending_reminders[:5]:
        label = f"{reminder.get('title', '')} ({reminder.get('due_at', '')})"
        done_col, title_col = st.columns([1, 4])
        with title_col:
            st.caption(label)
        with done_col:
            if st.button(
                t("dashboard.mark_done", language),
                key=f"reminder_done_{reminder.get('reminder_id')}",
                use_container_width=True,
            ):
                updated = []
                for item in reminders:
                    if item.get("reminder_id") == reminder.get("reminder_id"):
                        item = {**item, "status": "done", "completed_at_utc": datetime.utcnow().isoformat(timespec="seconds")}
                    updated.append(item)
                update_active_course_bucket(reminders=updated)
                touch_activity()
                _sync_reminders(
                    reminders=updated,
                    course_name=current_context.get("active_course_name"),
                    memory_agent=memory_agent,
                    student_email=student_email,
                    student_name=student_name,
                    language=language,
                )
                st.success(t("dashboard.reminder_done", language))
                st.rerun()


def _render_quiz_trend(quiz_attempts: list[dict[str, Any]], language: str) -> None:
    st.markdown(f"### {t('dashboard.quiz_trend', language)}")
    if quiz_attempts:
        quiz_df = pd.DataFrame(quiz_attempts)
        st.line_chart(quiz_df["score_percent"], use_container_width=True)
        st.dataframe(quiz_df, use_container_width=True, hide_index=True)
    else:
        st.info(t("dashboard.no_quizzes", language))


def _render_plan_overview(current_context: dict[str, Any], language: str) -> None:
    st.markdown(f"### {t('dashboard.plan_overview', language)}")
    active_plan = current_context.get("active_plan")
    if active_plan:
        plan_df = pd.DataFrame(active_plan["tasks"])
        topic_hours = plan_df.groupby("topic", as_index=False)["hours"].sum()
        st.bar_chart(topic_hours.set_index("topic"), use_container_width=True)
        st.dataframe(
            topic_hours.sort_values(by="hours", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "topic": st.column_config.TextColumn(t("dashboard.col.topic", language), width="large"),
                "hours": st.column_config.NumberColumn(t("dashboard.col.hours", language), format="%.1f h"),
            },
        )
    else:
        st.info(t("dashboard.no_plan", language))


def _render_chat_summary(chat_summaries: list[dict[str, Any]], language: str) -> None:
    if chat_summaries:
        with st.expander(t("chat.latest_summary", language), expanded=False):
            latest_summary = chat_summaries[-1]
            st.write(latest_summary.get("summary", ""))
            if latest_summary.get("main_topics"):
                st.caption(", ".join(latest_summary["main_topics"]))


def _render_memory_snapshot(
    memory_agent: Any,
    memory_status: dict[str, Any],
    student_email: str | None,
    student_name: str | None,
    language: str,
) -> None:
    with st.expander(t("dashboard.snapshot", language), expanded=False):
        if not memory_status["enabled"]:
            st.info(t("dashboard.configure_memory", language))
            return

        snapshot_result = memory_agent.get_snapshot(
            student_email=student_email,
            student_name=student_name,
        )
        if not snapshot_result["ok"]:
            st.warning(snapshot_result["reason"])
            return

        snapshot = snapshot_result["snapshot"]
        st.markdown(f"#### {t('dashboard.weak_topics', language)}")
        weak_topics = snapshot.get("weak_topics", [])
        if weak_topics:
            st.dataframe(pd.DataFrame(weak_topics), hide_index=True, use_container_width=True)
        else:
            st.info(t("dashboard.no_weak_topics", language))
        if snapshot.get("reminders"):
            st.markdown(f"#### {t('dashboard.reminders', language)}")
            st.dataframe(pd.DataFrame(snapshot["reminders"]), hide_index=True, use_container_width=True)


def _sync_reminders(
    *,
    reminders: list[dict[str, Any]],
    course_name: str | None,
    memory_agent: Any,
    student_email: str | None,
    student_name: str | None,
    language: str,
) -> None:
    sync_result = memory_agent.sync_reminders(
        course_name=course_name,
        reminders=reminders,
        student_email=student_email,
        student_name=student_name,
    )
    if sync_result["ok"]:
        st.info(t("dashboard.reminders_synced", language))
    else:
        st.warning(t("dashboard.reminders_local_only", language, reason=sync_result["reason"]))


def _overall_metrics(all_courses: list[dict[str, Any]]) -> dict[str, Any]:
    total_quiz_attempts = sum(course.get("quiz_attempts", 0) for course in all_courses)
    weighted_score = sum(course.get("average_score", 0.0) * course.get("quiz_attempts", 0) for course in all_courses)
    average_score = round(weighted_score / total_quiz_attempts, 1) if total_quiz_attempts else 0.0
    return {
        "courses": len(all_courses),
        "completed_tasks": sum(course.get("completed_tasks", 0) for course in all_courses),
        "upcoming_tasks": sum(course.get("upcoming_tasks", 0) for course in all_courses),
        "average_score": average_score,
        "uploads": sum(course.get("uploads", 0) for course in all_courses),
        "pending_reminders": sum(course.get("pending_reminders", 0) for course in all_courses),
    }


def _average_score(quiz_attempts: list[dict[str, Any]]) -> float:
    if not quiz_attempts:
        return 0.0
    return round(sum(item["score_percent"] for item in quiz_attempts) / len(quiz_attempts), 1)


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value[:16])
    except ValueError:
        return None
