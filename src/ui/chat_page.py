from pathlib import Path

import streamlit as st

from src.tools.state import touch_activity
from src.ui.theme import render_page_hero


def _assistant_reply(user_message: str) -> str:
    message = user_message.lower()
    active_plan = st.session_state.get("active_plan")

    if "study today" in message or "what should i study" in message:
        if not active_plan:
            return "I do not have a study plan yet. Open the Study Plan page and generate one first."

        upcoming_tasks = [task for task in active_plan["tasks"] if not task["completed"]]
        if not upcoming_tasks:
            return "Nice work. You completed all tasks in the current plan. Generate a fresh revision plan."

        task = upcoming_tasks[0]
        return f"Today focus on {task['topic']} ({task['hours']}h). Goal: {task['task']}."

    if "weak" in message:
        return "I can prioritize weak topics in your schedule. Add them in the Study Plan page."

    return "I am ready to help with planning, revision, and quizzes. Ask me what to study next."


def render_chat_page(project_root: Path) -> None:
    del project_root

    render_page_hero(
        "Study Coach Chat",
        "Ask for daily guidance, revision priorities, and next-step recommendations from your planner.",
        chips=[
            f"Messages: {len(st.session_state.chat_history)}",
            f"Active plan: {'Yes' if st.session_state.active_plan else 'No'}",
        ],
        accent_chip="Conversation mode",
    )

    chat_col, insights_col = st.columns([2.2, 1], gap="large")

    with chat_col:
        conversation = st.container(border=True)
        with conversation:
            if not st.session_state.chat_history:
                st.info("No messages yet. Try: What should I study today?")
            else:
                for item in st.session_state.chat_history:
                    with st.chat_message(item["role"]):
                        st.markdown(item["content"])

    with insights_col:
        st.markdown("#### Quick prompts")
        quick_prompt = st.pills(
            "Pick a prompt",
            options=[
                "What should I study today?",
                "Focus on my weak topics",
                "Give me a quick revision checklist",
            ],
            selection_mode="single",
            default=None,
            label_visibility="collapsed",
            width="stretch",
        )

        if st.button("Use selected prompt", width="stretch", disabled=quick_prompt is None):
            st.session_state.chat_history.append({"role": "user", "content": quick_prompt})
            st.session_state.chat_history.append({"role": "assistant", "content": _assistant_reply(quick_prompt)})
            touch_activity()
            st.rerun()

        st.markdown("#### Session snapshot")
        st.metric("Total messages", len(st.session_state.chat_history), border=True)
        st.metric(
            "Stored plans",
            len(st.session_state.study_plans),
            border=True,
        )
        if st.button("Clear chat history", width="stretch"):
            st.session_state.chat_history = []
            touch_activity()
            st.rerun()

    user_text = st.chat_input("Ask your study assistant...")
    if user_text:
        st.session_state.chat_history.append({"role": "user", "content": user_text})
        reply = _assistant_reply(user_text)
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        touch_activity()
        st.rerun()
