from pathlib import Path

import pandas as pd
import streamlit as st

from src.localization import t
from src.retrieval import CourseMaterialIndexer
from src.tools.semantic_cache import SemanticResponseCache
from src.tools.state import course_context, get_active_course, get_authenticated_user, get_memory_agent, get_selected_language
from src.ui.theme import render_page_hero


def render_dashboard_page(project_root: Path) -> None:
    language = get_selected_language()
    active_course = get_active_course()
    current_context = course_context()
    study_plans = current_context.get("study_plans", [])
    quiz_attempts = current_context.get("quiz_attempts", [])
    uploads = current_context.get("uploads", [])
    indexer = CourseMaterialIndexer(
        uploads_dir=project_root / "data" / "uploads",
        vector_store_dir=project_root / "data" / "vector_store",
    )
    retrieval_stats = indexer.stats(course_id=active_course["id"] if active_course else None)
    cache_stats = SemanticResponseCache().stats()
    memory_status = get_memory_agent().status()
    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None

    average_quiz = 0.0
    if quiz_attempts:
        average_quiz = round(sum(item["score_percent"] for item in quiz_attempts) / len(quiz_attempts), 1)

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
        ],
        accent_chip=t("dashboard.accent", language),
        language=language,
    )

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric(t("dashboard.plans_created", language), len(study_plans), border=True)
    col2.metric(t("dashboard.quiz_attempts", language), len(quiz_attempts), border=True)
    col3.metric(t("dashboard.average_score", language), f"{average_quiz}%", border=True)
    col4.metric(t("dashboard.uploaded_files", language), len(uploads), border=True)
    col5.metric(t("dashboard.rag_chunks", language), retrieval_stats["chunks"], border=True)
    col6.metric(t("dashboard.cache_entries", language), cache_stats["entries"], border=True)

    st.caption(
        t("dashboard.memory_connected", language)
        if memory_status["enabled"]
        else t("dashboard.memory_status", language, reason=memory_status["reason"])
    )

    st.markdown(f"### {t('dashboard.quiz_trend', language)}")
    if quiz_attempts:
        quiz_df = pd.DataFrame(quiz_attempts)
        st.line_chart(quiz_df["score_percent"], use_container_width=True)
        st.dataframe(quiz_df, use_container_width=True, hide_index=True)
    else:
        st.info(t("dashboard.no_quizzes", language))

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

    with st.expander(t("dashboard.snapshot", language), expanded=False):
        if not memory_status["enabled"]:
            st.info(t("dashboard.configure_memory", language))
        else:
            snapshot_result = get_memory_agent().get_snapshot(
                student_email=student_email,
                student_name=student_name,
            )
            if not snapshot_result["ok"]:
                st.warning(snapshot_result["reason"])
            else:
                snapshot = snapshot_result["snapshot"]
                st.markdown(f"#### {t('dashboard.weak_topics', language)}")
                weak_topics = snapshot.get("weak_topics", [])
                if weak_topics:
                    st.dataframe(pd.DataFrame(weak_topics), hide_index=True, use_container_width=True)
                else:
                    st.info(t("dashboard.no_weak_topics", language))
