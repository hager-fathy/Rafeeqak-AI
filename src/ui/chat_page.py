from pathlib import Path

import streamlit as st

from src.localization import t
from src.tools.state import (
    course_context,
    get_active_course,
    get_authenticated_user,
    get_memory_agent,
    get_selected_language,
    get_supervisor_agent,
    require_active_course_message,
    touch_activity,
    update_active_course_bucket,
    upsert_active_chat_summary,
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
    if result["agent"] == "quiz_generator_agent" and result.get("payload", {}).get("quiz"):
        generated_questions = context.get("generated_questions", [])
        generated_questions.extend(question["question"] for question in result["payload"].get("questions", []))
        update_active_course_bucket(
            current_quiz=result["payload"]["quiz"],
            last_quiz_feedback=None,
            generated_questions=generated_questions[-120:],
        )
    if result["agent"] == "reminder_agent" and result.get("payload", {}).get("reminders") is not None:
        update_active_course_bucket(reminders=result["payload"]["reminders"])
        auth_user = get_authenticated_user()
        get_memory_agent().sync_reminders(
            course_name=context.get("active_course_name"),
            reminders=result["payload"]["reminders"],
            student_email=auth_user.get("email") if auth_user else None,
            student_name=(auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None,
        )
    return result["response"]


def _record_session_summary(chat_history: list[dict]) -> None:
    context = course_context()
    active_course = context["active_course"]
    if active_course is None or not chat_history:
        return

    auth_user = get_authenticated_user()
    student_email = auth_user.get("email") if auth_user else None
    student_name = (auth_user.get("user_metadata") or {}).get("full_name") if auth_user else None
    result = get_memory_agent().summarize_chat_session(
        course_id=active_course["id"],
        course_name=active_course["name"],
        messages=chat_history,
        language=get_selected_language(),
        student_email=student_email,
        student_name=student_name,
    )
    if result["ok"]:
        upsert_active_chat_summary(result["summary"])


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
            _record_session_summary(chat_history)
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
        chat_summaries = current_context.get("chat_summaries", [])
        if chat_summaries:
            latest_summary = chat_summaries[-1]
            st.markdown(f"#### {t('chat.latest_summary', language)}")
            st.write(latest_summary.get("summary", ""))
            if latest_summary.get("next_steps"):
                st.caption(t("chat.next_steps", language))
                for step in latest_summary["next_steps"][:3]:
                    st.caption(f"- {step}")
        if st.button(t("chat.clear", language), use_container_width=True):
            update_active_course_bucket(chat_history=[], chat_summaries=[])
            touch_activity()
            st.rerun()

    user_text = st.chat_input(t("chat.input", language), disabled=active_course is None)
    if user_text:
        chat_history.append({"role": "user", "content": user_text})
        reply = _assistant_reply(user_text)
        chat_history.append({"role": "assistant", "content": reply})
        _record_session_summary(chat_history)
        update_active_course_bucket(chat_history=chat_history)
        touch_activity()
        st.rerun()
