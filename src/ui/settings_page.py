from __future__ import annotations

from datetime import time
from pathlib import Path

import streamlit as st

from src.auth import AuthService
from src.localization import LANGUAGE_LABELS, SUPPORTED_LANGUAGES, t
from src.tools.state import (
    get_authenticated_user,
    get_memory_agent,
    get_selected_language,
    get_user_settings,
    update_user_settings,
)
from src.ui.theme import render_page_hero


QUESTION_TYPES = ["mcq", "true_false", "short_answer", "matching"]
DIFFICULTIES = ["easy", "medium", "hard"]
STUDY_PREFERENCES = ["balanced", "deep_focus", "practice_first", "exam_revision"]
REMINDER_TYPES = ["lecture", "revision", "quiz", "missed_task", "deadline", "study_task", "custom"]


def render_settings_page(project_root: Path) -> None:
    del project_root
    language = get_selected_language()
    settings = get_user_settings()
    user = get_authenticated_user()
    metadata = user.get("user_metadata", {}) if user else {}
    stored_name = settings.get("full_name") or metadata.get("full_name") or ""
    quiz_difficulty_label = t(f"quiz.difficulty.{settings['default_quiz_difficulty']}", language)

    render_page_hero(
        t("settings.title", language),
        t("settings.subtitle", language),
        chips=[
            t("settings.daily_hours", language) + f": {settings['daily_study_hours']}",
            t("settings.default_quiz_difficulty", language) + f": {quiz_difficulty_label}",
            t("dashboard.reminders", language)
            + f": {t('common.yes', language) if settings['reminder_preferences']['enabled'] else t('common.no', language)}",
        ],
        accent_chip=t("settings.accent", language),
        language=language,
    )

    profile_col, defaults_col = st.columns([1, 1.4], gap="large")
    with profile_col:
        with st.container(border=True):
            st.markdown(f"#### {t('settings.profile', language)}")
            full_name = st.text_input(t("settings.full_name", language), value=stored_name)
            preferred_language = st.selectbox(
                t("settings.language", language),
                options=list(SUPPORTED_LANGUAGES),
                index=list(SUPPORTED_LANGUAGES).index(settings["preferred_language"]),
                format_func=lambda option: LANGUAGE_LABELS[option],
            )
            study_preference = st.selectbox(
                t("settings.study_preference", language),
                options=STUDY_PREFERENCES,
                index=STUDY_PREFERENCES.index(settings["study_preference"]),
                format_func=lambda option: t(f"settings.study.{option}", language),
            )

    with defaults_col:
        study_col, quiz_col = st.columns(2, gap="large")
        with study_col:
            with st.container(border=True):
                st.markdown(f"#### {t('settings.study_defaults', language)}")
                daily_study_hours = st.number_input(
                    t("settings.daily_hours", language),
                    min_value=0.5,
                    max_value=12.0,
                    value=float(settings["daily_study_hours"]),
                    step=0.5,
                )
                default_course_difficulty = st.selectbox(
                    t("settings.default_course_difficulty", language),
                    options=DIFFICULTIES,
                    index=DIFFICULTIES.index(settings["default_course_difficulty"]),
                    format_func=lambda option: t(f"quiz.difficulty.{option}", language),
                )
        with quiz_col:
            with st.container(border=True):
                st.markdown(f"#### {t('settings.quiz_defaults', language)}")
                default_quiz_difficulty = st.selectbox(
                    t("settings.default_quiz_difficulty", language),
                    options=DIFFICULTIES,
                    index=DIFFICULTIES.index(settings["default_quiz_difficulty"]),
                    format_func=lambda option: t(f"quiz.difficulty.{option}", language),
                )
                default_question_types = st.multiselect(
                    t("settings.question_types", language),
                    options=QUESTION_TYPES,
                    default=settings["default_question_types"],
                    format_func=lambda option: t(f"quiz.type.{option}", language),
                )

    reminder_preferences = settings["reminder_preferences"]
    with st.container(border=True):
        st.markdown(f"#### {t('settings.reminder_defaults', language)}")
        enabled_col, time_col, types_col = st.columns([1, 1, 2], gap="large")
        with enabled_col:
            reminders_enabled = st.toggle(
                t("settings.reminders_enabled", language),
                value=bool(reminder_preferences["enabled"]),
            )
            reminder_lead_days = st.number_input(
                t("settings.reminder_lead_days", language),
                min_value=0,
                max_value=14,
                value=int(reminder_preferences["lead_days"]),
                step=1,
            )
        with time_col:
            reminder_time = st.time_input(
                t("settings.reminder_time", language),
                value=_parse_time(reminder_preferences["reminder_time"]),
            )
        with types_col:
            reminder_types = st.multiselect(
                t("settings.reminder_types", language),
                options=REMINDER_TYPES,
                default=reminder_preferences["types"],
                format_func=lambda option: t(f"settings.reminder_type.{option}", language),
            )

    if st.button(t("settings.save", language), type="primary", use_container_width=True):
        saved_settings = update_user_settings(
            {
                "full_name": " ".join(full_name.split()),
                "preferred_language": preferred_language,
                "daily_study_hours": float(daily_study_hours),
                "default_course_difficulty": default_course_difficulty,
                "default_quiz_difficulty": default_quiz_difficulty,
                "default_question_types": default_question_types,
                "study_preference": study_preference,
                "reminder_preferences": {
                    "enabled": reminders_enabled,
                    "lead_days": int(reminder_lead_days),
                    "reminder_time": reminder_time.strftime("%H:%M"),
                    "types": reminder_types,
                },
            }
        )
        _update_local_auth_user(saved_settings["full_name"])
        st.success(t("settings.saved", language))
        _sync_settings_to_cloud(saved_settings, user=user, language=language)


def _parse_time(value: str) -> time:
    try:
        hour, minute = str(value).split(":", 1)
        return time(int(hour), int(minute))
    except (TypeError, ValueError):
        return time(18, 0)


def _update_local_auth_user(full_name: str) -> None:
    user = get_authenticated_user()
    if not user:
        return
    metadata = dict(user.get("user_metadata") or {})
    metadata["full_name"] = full_name
    user["user_metadata"] = metadata
    st.session_state["auth_user"] = user


def _sync_settings_to_cloud(settings: dict, *, user: dict | None, language: str) -> None:
    if not user:
        return
    student_email = user.get("email")
    student_name = settings.get("full_name") or (user.get("user_metadata") or {}).get("full_name")

    auth_service = AuthService()
    auth_result = auth_service.update_profile(full_name=str(settings.get("full_name") or ""))
    if auth_result["ok"] and auth_result.get("user"):
        st.session_state["auth_user"] = auth_result["user"]
        st.info(t("settings.auth_synced", language))
    elif not auth_result["ok"] and auth_service.is_available:
        st.warning(t("settings.auth_local", language, reason=auth_result["message"]))

    sync_result = get_memory_agent().save_user_settings(
        settings=settings,
        student_email=student_email,
        student_name=student_name,
    )
    if sync_result["ok"]:
        st.info(t("settings.cloud_saved", language))
    else:
        st.warning(t("settings.local_only", language, reason=sync_result["reason"]))
