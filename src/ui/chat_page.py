from pathlib import Path

import streamlit as st

from src.tools.state import append_route_trace, get_memory_agent, get_supervisor_agent, touch_activity
from src.ui.theme import render_page_hero


def _assistant_reply(user_message: str) -> str:
    result = get_supervisor_agent().handle_message(
        user_message,
        context={
            "active_plan": st.session_state.get("active_plan"),
            "study_plans": st.session_state.get("study_plans", []),
            "quiz_attempts": st.session_state.get("quiz_attempts", []),
            "uploads": st.session_state.get("uploads", []),
        },
        memory_agent=get_memory_agent(),
    )
    append_route_trace(result["trace"])
    if result["agent"] == "quiz_generator_agent" and result.get("payload", {}).get("quiz"):
        st.session_state.current_quiz = result["payload"]["quiz"]
        st.session_state.last_quiz_feedback = None
    return result["response"]


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
        route_traces = st.session_state.get("route_traces", [])
        st.metric("Route traces", len(route_traces), border=True)
        if route_traces:
            with st.expander("Latest route trace", expanded=False):
                for step in route_traces[-1]:
                    st.caption(f"{step['agent']} | {step['step']} | {step['status']}")
                    st.write(step["action"])
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
