from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src.tools.state import (
    append_route_trace,
    get_authenticated_user,
    get_memory_agent,
    get_supervisor_agent,
    touch_activity,
)
from src.ui.theme import render_page_hero


def _parse_topics(raw_text: str) -> list[str]:
    return [item.strip() for item in raw_text.split(",") if item.strip()]


def render_study_plan_page(project_root: Path) -> None:
    del project_root
    memory_agent = get_memory_agent()
    memory_status = memory_agent.status()
    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None

    render_page_hero(
        "Personalized Study Plan",
        "Create an exam-focused schedule with weighted weak-topic coverage and recurring checkpoints.",
        chips=[
            f"Saved plans: {len(st.session_state.study_plans)}",
            f"Current day: {date.today().isoformat()}",
        ],
        accent_chip="Planner",
    )

    input_col, summary_col = st.columns([1.8, 1], gap="large")

    with input_col:
        with st.container(border=True):
            st.markdown("#### Plan configuration")
            with st.form("plan_form"):
                course_name = st.text_input("Course name", value="Machine Learning")
                exam_date = st.date_input("Exam date", value=date.today() + timedelta(days=10), min_value=date.today())
                daily_hours = st.number_input("Available study hours per day", min_value=0.5, max_value=12.0, value=2.0, step=0.5)
                weak_topics_input = st.text_input("Weak topics (comma-separated)", value="SVM, Backpropagation")
                other_topics_input = st.text_input("Other topics (comma-separated)", value="Linear Regression, Decision Trees")
                submit_plan = st.form_submit_button("Generate study plan", width="stretch")

    with summary_col:
        with st.container(border=True):
            st.markdown("#### Planning insights")
            active_plan = st.session_state.get("active_plan")
            if active_plan:
                total_tasks = len(active_plan["tasks"])
                weak_count = len(active_plan["weak_topics"])
                st.metric("Tasks queued", total_tasks, border=True)
                st.metric("Weak topics tracked", weak_count, border=True)
                st.metric("Hours/day", active_plan["daily_hours"], border=True)
            else:
                st.info("Generate your first plan to view plan intelligence.")
            st.metric("Supabase memory", "Connected" if memory_status["enabled"] else "Not configured", border=True)

    if submit_plan:
        weak_topics = _parse_topics(weak_topics_input)
        other_topics = _parse_topics(other_topics_input)
        plan_result = get_supervisor_agent().create_study_plan(
            {
                "course_name": course_name,
                "exam_date": exam_date,
                "daily_hours": daily_hours,
                "weak_topics": weak_topics,
                "other_topics": other_topics,
            },
            memory_agent=memory_agent,
            student_email=student_email,
            student_name=student_name,
        )
        append_route_trace(plan_result["trace"])
        plan = plan_result["plan"]
        st.session_state.study_plans.append(plan)
        st.session_state.active_plan = plan
        touch_activity()
        st.success(plan_result["summary"])

        sync_result = plan_result["sync_result"]
        if sync_result["ok"]:
            st.info("Study plan synced to Supabase memory.")
        else:
            st.warning(f"Study plan saved locally only. Reason: {sync_result['reason']}")

    active_plan = st.session_state.get("active_plan")
    if not active_plan:
        st.info("No active plan yet. Generate one above.")
        return

    tasks_df = pd.DataFrame(active_plan["tasks"])
    st.markdown("### Current plan timeline")
    st.dataframe(
        tasks_df,
        width="stretch",
        hide_index=True,
        column_config={
            "date": st.column_config.TextColumn("Study Date", width="small"),
            "topic": st.column_config.TextColumn("Topic", width="medium"),
            "hours": st.column_config.NumberColumn("Hours", format="%.1f h"),
            "checkpoint": st.column_config.CheckboxColumn("Quiz Checkpoint"),
            "completed": st.column_config.CheckboxColumn("Completed"),
        },
    )
