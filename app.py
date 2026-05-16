from datetime import datetime, timedelta

import streamlit as st

from src.config import PROJECT_ROOT, load_project_env

load_project_env()

from src.auth import AuthService
from src.auth.session_persistence import restore_authenticated_session
from src.localization import LANGUAGE_LABELS, SUPPORTED_LANGUAGES, t
from src.retrieval import CourseMaterialIndexer
from src.tools.llm_client import LLMSettings, get_llm_settings, log_gemini_key_status
from src.tools.state import (
    add_course,
    course_context,
    delete_course,
    get_active_course,
    get_authenticated_user,
    get_courses,
    get_memory_agent,
    get_selected_language,
    init_state,
    mark_language_profile_loaded,
    rename_course,
    set_active_course,
    set_selected_language,
    should_load_language_from_profile,
)
from src.ui.account_page import render_account_page
from src.ui.chat_page import render_chat_page
from src.ui.dashboard_page import render_dashboard_page
from src.ui.login_page import render_login_page
from src.ui.quiz_page import render_quiz_page
from src.ui.signup_page import render_signup_page
from src.ui.study_plan_page import render_study_plan_page
from src.ui.settings_page import render_settings_page
from src.ui.theme import inject_global_styles
from src.ui.upload_page import render_upload_page

UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"
VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vector_store"


def ensure_directories() -> None:
    for directory in (UPLOADS_DIR, VECTOR_STORE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def _initialize_gemini_config() -> LLMSettings:
    settings = get_llm_settings()
    st.session_state["gemini_config"] = {
        "configured": settings.is_configured,
        "model": settings.model,
    }
    debug_status = (settings.is_configured, settings.model)
    if st.session_state.get("_gemini_debug_status") != debug_status:
        log_gemini_key_status(settings)
        st.session_state["_gemini_debug_status"] = debug_status
    return settings


def _render_gemini_config_warning(settings: LLMSettings, language: str) -> None:
    if settings.is_configured:
        return
    st.warning(t("llm.gemini_missing", language, model=settings.model))


def main() -> None:
    st.set_page_config(
        page_title=t("app.title", "en"),
        page_icon=":books:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    ensure_directories()
    init_state()
    gemini_settings = _initialize_gemini_config()
    memory_agent = get_memory_agent()
    auth_service = AuthService()

    restore_authenticated_session(auth_service)

    user = get_authenticated_user()
    if user:
        _load_language_from_profile_once(memory_agent, user)
    language = get_selected_language()
    inject_global_styles(language)
    _render_gemini_config_warning(gemini_settings, language)

    if user:
        pages = {
            "chat": {
                "label": t("page.chat.label", language),
                "hint": t("page.chat.hint", language),
                "handler": render_chat_page,
            },
            "study_plan": {
                "label": t("page.study_plan.label", language),
                "hint": t("page.study_plan.hint", language),
                "handler": render_study_plan_page,
            },
            "upload_materials": {
                "label": t("page.upload_materials.label", language),
                "hint": t("page.upload_materials.hint", language),
                "handler": render_upload_page,
            },
            "quiz": {
                "label": t("page.quiz.label", language),
                "hint": t("page.quiz.hint", language),
                "handler": render_quiz_page,
            },
            "progress_dashboard": {
                "label": t("page.progress_dashboard.label", language),
                "hint": t("page.progress_dashboard.hint", language),
                "handler": render_dashboard_page,
            },
            "settings": {
                "label": t("page.settings.label", language),
                "hint": t("page.settings.hint", language),
                "handler": render_settings_page,
            },
            "account": {
                "label": t("page.account.label", language),
                "hint": t("page.account.hint", language),
                "handler": render_account_page,
            },
        }
    else:
        pages = {
            "login": {
                "label": t("page.login.label", language),
                "hint": t("page.login.hint", language),
                "handler": render_login_page,
            },
            "signup": {
                "label": t("page.signup.label", language),
                "hint": t("page.signup.hint", language),
                "handler": render_signup_page,
            },
        }

    if "selected_page" not in st.session_state:
        st.session_state.selected_page = list(pages.keys())[0]
    if st.session_state.selected_page not in pages:
        st.session_state.selected_page = list(pages.keys())[0]

    nav_col_left, nav_col_center, nav_col_right = st.columns([1, 2.8, 1], gap="small")
    with nav_col_left:
        st.markdown(f"<div class='top-nav-title'>{t('nav.language', language)}</div>", unsafe_allow_html=True)
        selected_language = st.segmented_control(
            t("nav.language_picker", language),
            options=list(SUPPORTED_LANGUAGES),
            default=language,
            format_func=lambda option: LANGUAGE_LABELS[option],
            selection_mode="single",
            label_visibility="collapsed",
            key="language_selector",
        )
        if selected_language and selected_language != get_selected_language():
            set_selected_language(selected_language)
            st.session_state["language_sync_notice"] = _save_language_preference(
                memory_agent=memory_agent,
                user=user,
                language=selected_language,
            )
            st.rerun()
        sync_notice = st.session_state.pop("language_sync_notice", None)
        if sync_notice:
            st.caption(sync_notice)

    with nav_col_center:
        st.markdown(f"<div class='top-nav-title'>{t('nav.title', language)}</div>", unsafe_allow_html=True)
        selected_page = st.segmented_control(
            t("nav.go_to", language),
            options=list(pages.keys()),
            default=st.session_state.selected_page,
            format_func=lambda option: pages[option]["label"],
            selection_mode="single",
            label_visibility="collapsed",
            key="top_nav_selector",
        )
        if selected_page is None:
            selected_page = st.session_state.selected_page
        st.session_state.selected_page = selected_page

    if user:
        courses = get_courses()
        active_course = get_active_course()
        course_ids = [course["id"] for course in courses]
        course_col, new_course_col = st.columns([1.5, 1], gap="small")
        with course_col:
            st.markdown(f"<div class='top-nav-title'>{t('nav.active_course', language)}</div>", unsafe_allow_html=True)
            selected_course_id = st.selectbox(
                t("nav.active_course_label", language),
                options=course_ids,
                index=(
                    course_ids.index(active_course["id"])
                    if active_course and active_course["id"] in course_ids
                    else None
                ),
                format_func=lambda course_id: next(
                    (course["name"] for course in courses if course["id"] == course_id),
                    t("course.none_selected", language),
                ),
                placeholder=t("nav.select_course_placeholder", language),
                label_visibility="collapsed",
            )
            if selected_course_id and selected_course_id != st.session_state.get("active_course_id"):
                set_active_course(selected_course_id)
                st.rerun()
        with new_course_col:
            with st.form("quick_course_form", border=False):
                course_name = st.text_input(
                    t("nav.new_course", language),
                    placeholder=t("nav.new_course_placeholder", language),
                    label_visibility="collapsed",
                )
                submitted = st.form_submit_button(t("nav.add_course", language), use_container_width=True)
                if submitted:
                    course = add_course(course_name)
                    if course is None:
                        st.warning(t("nav.enter_course_name", language))
                    else:
                        st.success(t("nav.active_course_success", language, course_name=course["name"]))
                        st.rerun()
        _render_course_management(courses, active_course, language)
        _render_reminder_notifications(language)
    pages[selected_page]["handler"](project_root=PROJECT_ROOT)


def _render_course_management(courses: list[dict], active_course: dict | None, language: str) -> None:
    with st.expander(t("nav.manage_courses", language), expanded=False):
        if not courses:
            st.info(t("nav.no_courses", language))
            return

        selected_id = st.selectbox(
            t("nav.manage_course_label", language),
            options=[course["id"] for course in courses],
            index=(
                [course["id"] for course in courses].index(active_course["id"])
                if active_course and active_course["id"] in [course["id"] for course in courses]
                else 0
            ),
            format_func=lambda course_id: next(
                (course["name"] for course in courses if course["id"] == course_id),
                t("course.none_selected", language),
            ),
        )
        selected_course = next((course for course in courses if course["id"] == selected_id), None)
        if selected_course is None:
            st.warning(t("nav.course_missing", language))
            return

        rename_col, delete_col = st.columns([1.4, 1], gap="large")
        with rename_col:
            with st.form(f"rename_course_{selected_id}", border=False):
                new_name = st.text_input(
                    t("nav.rename_course_name", language),
                    value=selected_course["name"],
                )
                submitted = st.form_submit_button(t("nav.save_course", language), use_container_width=True)
                if submitted:
                    result = rename_course(selected_id, new_name)
                    if result["ok"]:
                        _course_indexer().rename_course(
                            course_id=selected_id,
                            course_name=result["course"]["name"],
                        )
                        st.success(t("nav.course_renamed", language, course_name=result["course"]["name"]))
                        st.rerun()
                    else:
                        st.warning(_course_management_reason(result["reason"], language))

        with delete_col:
            st.caption(t("nav.delete_course_caption", language, course_name=selected_course["name"]))
            confirm_key = f"delete_course_confirm_{selected_id}"
            confirmed = st.checkbox(t("nav.delete_course_confirm", language), key=confirm_key)
            if st.button(
                t("nav.delete_course", language),
                use_container_width=True,
                disabled=not confirmed,
                key=f"delete_course_button_{selected_id}",
            ):
                try:
                    index_result = _course_indexer().remove_course(course_id=selected_id)
                except OSError as exc:
                    st.warning(t("nav.delete_course_failed", language, reason=str(exc)))
                    return

                if not index_result.get("ok", False):
                    st.warning(t("nav.delete_course_failed", language, reason=index_result.get("reason", "unknown")))
                    return

                result = delete_course(selected_id)
                if result["ok"]:
                    st.success(t("nav.course_deleted", language, course_name=result["course"]["name"]))
                    st.rerun()
                else:
                    st.warning(_course_management_reason(result["reason"], language))


def _course_indexer() -> CourseMaterialIndexer:
    return CourseMaterialIndexer(
        uploads_dir=UPLOADS_DIR,
        vector_store_dir=VECTOR_STORE_DIR,
    )


def _course_management_reason(reason: str, language: str) -> str:
    return {
        "empty_name": t("nav.enter_course_name", language),
        "duplicate_name": t("nav.duplicate_course_name", language),
        "missing_course": t("nav.course_missing", language),
    }.get(reason, reason)


def _render_reminder_notifications(language: str) -> None:
    context = course_context()
    reminders = context.get("reminders", []) or []
    now = datetime.now()
    due_soon = now + timedelta(hours=24)
    notifications = []
    for reminder in reminders:
        if not isinstance(reminder, dict) or reminder.get("status") == "done":
            continue
        due_at = _parse_reminder_datetime(reminder.get("due_at"))
        if due_at is None or due_at > due_soon:
            continue
        notifications.append((due_at, reminder))

    if not notifications:
        return

    with st.expander(t("dashboard.notifications", language), expanded=True):
        for due_at, reminder in sorted(notifications, key=lambda item: item[0])[:5]:
            message = t(
                "dashboard.notification_due",
                language,
                course=reminder.get("course_name")
                or context.get("active_course_name")
                or t("course.none_selected", language),
                title=reminder.get("title", ""),
                due_at=due_at.strftime("%Y-%m-%d %H:%M"),
            )
            if due_at <= now:
                st.warning(message)
            else:
                st.info(message)


def _parse_reminder_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value[:16])
    except ValueError:
        return None


def _load_language_from_profile_once(memory_agent, user: dict) -> None:
    if not should_load_language_from_profile():
        return

    student_email, student_name = _student_identity(user)
    if student_email:
        result = memory_agent.get_preferred_language(
            student_email=student_email,
            student_name=student_name,
        )
        if result["ok"]:
            set_selected_language(result.get("preferred_language"))
    mark_language_profile_loaded()


def _save_language_preference(*, memory_agent, user: dict | None, language: str) -> str:
    if not user:
        return t("nav.profile_language_local", get_selected_language())

    student_email, student_name = _student_identity(user)
    result = memory_agent.save_preferred_language(
        preferred_language=language,
        student_email=student_email,
        student_name=student_name,
    )
    current_language = get_selected_language()
    if result["ok"]:
        return t("nav.profile_language_saved", current_language)
    if not memory_agent.status()["enabled"]:
        return t("nav.profile_language_local", current_language)
    return t("nav.profile_language_failed", current_language, reason=result["reason"])


def _student_identity(user: dict) -> tuple[str | None, str | None]:
    metadata = user.get("user_metadata") or {}
    return user.get("email"), metadata.get("full_name")


if __name__ == "__main__":
    main()
