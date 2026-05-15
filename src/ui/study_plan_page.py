from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src.localization import t
from src.tools.state import (
    add_course,
    append_route_trace,
    course_context,
    get_active_course,
    get_authenticated_user,
    get_selected_language,
    get_memory_agent,
    get_supervisor_agent,
    touch_activity,
    update_active_course_bucket,
)
from src.ui.theme import render_page_hero


def _parse_topics(raw_text: str) -> list[str]:
    return [item.strip() for item in raw_text.split(",") if item.strip()]


def render_study_plan_page(project_root: Path) -> None:
    del project_root
    language = get_selected_language()
    memory_agent = get_memory_agent()
    memory_status = memory_agent.status()
    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None
    active_course = get_active_course()
    current_context = course_context()

    render_page_hero(
        t("planner.title", language),
        t("planner.subtitle", language),
        chips=[
            f"{t('planner.course_name', language)}: {active_course['name'] if active_course else t('course.none_selected', language)}",
            t("planner.saved_plans_chip", language, count=len(current_context["study_plans"])),
            t("planner.current_day_chip", language, date=date.today().isoformat()),
        ],
        accent_chip=t("planner.accent", language),
        language=language,
    )

    input_col, summary_col = st.columns([1.8, 1], gap="large")

    with input_col:
        with st.container(border=True):
            st.markdown(f"#### {t('planner.config', language)}")
            with st.form("plan_form"):
                course_name = st.text_input(
                    t("planner.course_name", language),
                    value=active_course["name"] if active_course else "",
                    placeholder=t("planner.course_placeholder", language),
                )
                exam_date = st.date_input(
                    t("planner.exam_date", language),
                    value=date.today() + timedelta(days=10),
                    min_value=date.today(),
                )
                daily_hours = st.number_input(
                    t("planner.daily_hours", language),
                    min_value=0.5,
                    max_value=12.0,
                    value=2.0,
                    step=0.5,
                )
                weak_topics_input = st.text_input(
                    t("planner.weak_topics", language),
                    placeholder=t("planner.weak_placeholder", language),
                )
                other_topics_input = st.text_input(
                    t("planner.other_topics", language),
                    placeholder=t("planner.other_placeholder", language),
                )
                submit_plan = st.form_submit_button(t("planner.generate", language), use_container_width=True)

    with summary_col:
        with st.container(border=True):
            st.markdown(f"#### {t('planner.insights', language)}")
            active_plan = current_context.get("active_plan")
            if active_plan:
                total_tasks = len(active_plan["tasks"])
                weak_count = len(active_plan["weak_topics"])
                st.metric(t("planner.tasks_queued", language), total_tasks, border=True)
                st.metric(t("planner.weak_tracked", language), weak_count, border=True)
                st.metric(t("planner.hours_day", language), active_plan["daily_hours"], border=True)
            else:
                st.info(t("planner.no_insights", language))
            st.metric(
                t("planner.supabase_memory", language),
                t("common.connected", language) if memory_status["enabled"] else t("common.not_configured", language),
                border=True,
            )

    if submit_plan:
        if active_course is None:
            active_course = add_course(course_name)
            current_context = course_context()
        if active_course is None:
            st.warning(t("planner.course_required", language))
            return

        weak_topics = _parse_topics(weak_topics_input)
        other_topics = _parse_topics(other_topics_input)
        plan_result = get_supervisor_agent().create_study_plan(
            {
                "course_name": active_course["name"],
                "exam_date": exam_date,
                "daily_hours": daily_hours,
                "weak_topics": weak_topics,
                "other_topics": other_topics,
                "language": language,
            },
            memory_agent=memory_agent,
            student_email=student_email,
            student_name=student_name,
        )
        append_route_trace(plan_result["trace"])
        plan = plan_result["plan"]
        study_plans = current_context["study_plans"]
        study_plans.append(plan)
        update_active_course_bucket(study_plans=study_plans, active_plan=plan)
        touch_activity()
        st.success(plan_result["summary"])

        sync_result = plan_result["sync_result"]
        if sync_result["ok"]:
            st.info(t("planner.synced", language))
        else:
            st.warning(t("planner.local_only", language, reason=sync_result["reason"]))

    active_plan = course_context().get("active_plan")
    if not active_plan:
        st.info(t("planner.no_plan", language))
        return

    tasks_df = pd.DataFrame(active_plan["tasks"])
    st.markdown(f"### {t('planner.timeline', language)}")
    st.dataframe(
        tasks_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "date": st.column_config.TextColumn(t("planner.col.study_date", language), width="small"),
            "topic": st.column_config.TextColumn(t("planner.col.topic", language), width="medium"),
            "phase": st.column_config.TextColumn(t("planner.col.phase", language), width="medium"),
            "hours": st.column_config.NumberColumn(t("planner.col.hours", language), format="%.1f h"),
            "checkpoint": st.column_config.CheckboxColumn(t("planner.col.checkpoint", language)),
            "completed": st.column_config.CheckboxColumn(t("planner.col.completed", language)),
        },
    )
