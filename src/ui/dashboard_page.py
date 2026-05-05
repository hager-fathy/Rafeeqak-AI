from pathlib import Path

import pandas as pd
import streamlit as st

from src.tools.state import get_authenticated_user, get_memory_agent
from src.ui.theme import render_page_hero


def render_dashboard_page(project_root: Path) -> None:
    del project_root

    study_plans = st.session_state.get("study_plans", [])
    quiz_attempts = st.session_state.get("quiz_attempts", [])
    uploads = st.session_state.get("uploads", [])
    memory_status = get_memory_agent().status()
    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None

    average_quiz = 0.0
    if quiz_attempts:
        average_quiz = round(sum(item["score_percent"] for item in quiz_attempts) / len(quiz_attempts), 1)

    render_page_hero(
        "Learning Operations Dashboard",
        "Monitor study execution, quiz quality, and material readiness from one analytics view.",
        chips=[
            f"Plans: {len(study_plans)}",
            f"Uploads: {len(uploads)}",
            f"Quiz avg: {average_quiz}%",
        ],
        accent_chip="Insights",
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Plans Created", len(study_plans), border=True)
    col2.metric("Quiz Attempts", len(quiz_attempts), border=True)
    col3.metric("Average Quiz Score", f"{average_quiz}%", border=True)
    col4.metric("Uploaded Files", len(uploads), border=True)

    st.caption("Supabase memory: connected" if memory_status["enabled"] else f"Supabase memory: {memory_status['reason']}")

    st.markdown("### Quiz Trend")
    if quiz_attempts:
        quiz_df = pd.DataFrame(quiz_attempts)
        st.line_chart(quiz_df["score_percent"], width="stretch")
        st.dataframe(quiz_df, width="stretch", hide_index=True)
    else:
        st.info("No quiz attempts yet.")

    st.markdown("### Active Plan Overview")
    active_plan = st.session_state.get("active_plan")
    if active_plan:
        plan_df = pd.DataFrame(active_plan["tasks"])
        topic_hours = plan_df.groupby("topic", as_index=False)["hours"].sum()
        st.bar_chart(topic_hours.set_index("topic"), width="stretch")
        st.dataframe(
            topic_hours.sort_values(by="hours", ascending=False),
            width="stretch",
            hide_index=True,
            column_config={
                "topic": st.column_config.TextColumn("Topic", width="large"),
                "hours": st.column_config.NumberColumn("Total Hours", format="%.1f h"),
            },
        )
    else:
        st.info("No active study plan yet.")

    with st.expander("Supabase memory snapshot", expanded=False):
        if not memory_status["enabled"]:
            st.info("Configure SUPABASE_URL and SUPABASE_KEY in .env to enable cloud memory.")
        else:
            snapshot_result = get_memory_agent().get_snapshot(
                student_email=student_email,
                student_name=student_name,
            )
            if not snapshot_result["ok"]:
                st.warning(snapshot_result["reason"])
            else:
                snapshot = snapshot_result["snapshot"]
                st.markdown("#### Weak topics (Top 10)")
                weak_topics = snapshot.get("weak_topics", [])
                if weak_topics:
                    st.dataframe(pd.DataFrame(weak_topics), hide_index=True, width="stretch")
                else:
                    st.info("No weak topics stored yet.")

    with st.expander("Agent route traces", expanded=False):
        route_traces = st.session_state.get("route_traces", [])
        if not route_traces:
            st.info("No agent route traces yet.")
        else:
            trace_rows = []
            for trace_index, trace in enumerate(route_traces[-10:], start=1):
                for step in trace:
                    trace_rows.append(
                        {
                            "trace": trace_index,
                            "time_utc": step["timestamp_utc"],
                            "agent": step["agent"],
                            "step": step["step"],
                            "status": step["status"],
                            "action": step["action"],
                        }
                    )
            st.dataframe(pd.DataFrame(trace_rows), width="stretch", hide_index=True)
