from pathlib import Path

import streamlit as st

from src.localization import t
from src.tools.state import (
    append_route_trace,
    course_context,
    get_active_course,
    get_authenticated_user,
    get_memory_agent,
    get_selected_language,
    get_supervisor_agent,
    require_active_course_message,
    touch_activity,
    update_active_course_bucket,
)
from src.ui.theme import render_page_hero


def _assistant_reply(user_message: str) -> str:
    context = course_context()
    context["auth_user"] = get_authenticated_user()
    context["require_active_course"] = True
    result = get_supervisor_agent().handle_message(
        user_message,
        context=context,
        memory_agent=get_memory_agent(),
    )
    append_route_trace(result["trace"])
    if result["agent"] == "quiz_generator_agent" and result.get("payload", {}).get("quiz"):
        generated_questions = context.get("generated_questions", [])
        generated_questions.extend(question["question"] for question in result["payload"].get("questions", []))
        update_active_course_bucket(
            current_quiz=result["payload"]["quiz"],
            last_quiz_feedback=None,
            generated_questions=generated_questions[-120:],
        )
    return result["response"]


def render_chat_page(project_root: Path) -> None:
    del project_root
    language = get_selected_language()
    active_course = get_active_course()
    current_context = course_context()
    chat_history = current_context["chat_history"]

    render_page_hero(
        t("chat.title", language),
        t("chat.subtitle", language),
        chips=[
            f"{t('planner.course_name', language)}: {active_course['name'] if active_course else t('course.none_selected', language)}",
            t("chat.messages_chip", language, count=len(chat_history)),
            t(
                "chat.active_plan_chip",
                language,
                status=t("common.yes", language) if current_context["active_plan"] else t("common.no", language),
            ),
        ],
        accent_chip=t("chat.accent", language),
        language=language,
    )

    course_warning = require_active_course_message()
    if course_warning:
        st.info(course_warning)

    chat_col, insights_col = st.columns([2.2, 1], gap="large")

    with chat_col:
        conversation = st.container(border=True)
        with conversation:
            if not chat_history:
                st.info(t("chat.empty", language))
            else:
                for item in chat_history:
                    with st.chat_message(item["role"]):
                        st.markdown(item["content"])

    with insights_col:
        st.markdown(f"#### {t('chat.quick_prompts', language)}")
        quick_prompt = st.pills(
            t("chat.pick_prompt", language),
            options=[
                t("chat.prompt.today", language),
                t("chat.prompt.weak", language),
                t("chat.prompt.checklist", language),
            ],
            selection_mode="single",
            default=None,
            label_visibility="collapsed",
        )

        if st.button(t("chat.use_prompt", language), use_container_width=True, disabled=quick_prompt is None or active_course is None):
            chat_history.append({"role": "user", "content": quick_prompt})
            chat_history.append({"role": "assistant", "content": _assistant_reply(quick_prompt)})
            update_active_course_bucket(chat_history=chat_history)
            touch_activity()
            st.rerun()

        st.markdown(f"#### {t('chat.snapshot', language)}")
        st.metric(t("chat.total_messages", language), len(chat_history), border=True)
        st.metric(
            t("chat.stored_plans", language),
            len(current_context["study_plans"]),
            border=True,
        )
        route_traces = st.session_state.get("route_traces", [])
        st.metric(t("chat.route_traces", language), len(route_traces), border=True)
        if route_traces:
            with st.expander(t("chat.latest_trace", language), expanded=False):
                for step in route_traces[-1]:
                    st.caption(f"{step['agent']} | {step['step']} | {step['status']}")
                    st.write(step["action"])
        if st.button(t("chat.clear", language), use_container_width=True):
            update_active_course_bucket(chat_history=[])
            touch_activity()
            st.rerun()

    user_text = st.chat_input(t("chat.input", language), disabled=active_course is None)
    if user_text:
        chat_history.append({"role": "user", "content": user_text})
        reply = _assistant_reply(user_text)
        chat_history.append({"role": "assistant", "content": reply})
        update_active_course_bucket(chat_history=chat_history)
        touch_activity()
        st.rerun()
