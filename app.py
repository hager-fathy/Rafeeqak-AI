from pathlib import Path

import streamlit as st

from src.auth import AuthService
from src.tools.state import (
    add_course,
    clear_authenticated_user,
    get_active_course,
    get_authenticated_user,
    get_courses,
    get_memory_agent,
    init_state,
    is_authenticated,
    set_authenticated_user,
    set_active_course,
)
from src.ui.account_page import render_account_page
from src.ui.chat_page import render_chat_page
from src.ui.dashboard_page import render_dashboard_page
from src.ui.login_page import render_login_page
from src.ui.quiz_page import render_quiz_page
from src.ui.signup_page import render_signup_page
from src.ui.study_plan_page import render_study_plan_page
from src.ui.theme import inject_global_styles
from src.ui.upload_page import render_upload_page

PROJECT_ROOT = Path(__file__).resolve().parent
UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"
VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vector_store"


def ensure_directories() -> None:
    for directory in (UPLOADS_DIR, VECTOR_STORE_DIR):
        directory.mkdir(parents=True, exist_ok=True)

def main() -> None:
    st.set_page_config(
        page_title="Smart Study Planner",
        page_icon=":books:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    inject_global_styles()
    ensure_directories()
    init_state()
    memory_status = get_memory_agent().status()
    auth_service = AuthService()

    # Restore auth session tokens on rerun if available.
    if auth_service.is_available and not is_authenticated():
        access_token = st.session_state.get("auth_access_token")
        refresh_token = st.session_state.get("auth_refresh_token")
        if access_token and refresh_token:
            restored = auth_service.restore_session(
                access_token=access_token,
                refresh_token=refresh_token,
            )
            if restored["ok"] and restored.get("user"):
                set_authenticated_user(
                    user=restored["user"],
                    access_token=access_token,
                    refresh_token=refresh_token,
                )
            elif not restored["ok"]:
                clear_authenticated_user()

    user = get_authenticated_user()

    if user:
        pages = {
            "chat": {
                "label": "Chat",
                "hint": "Ask what to study and get quick coaching.",
                "handler": render_chat_page,
            },
            "study_plan": {
                "label": "Study Plan",
                "hint": "Create your schedule from exam date and weak topics.",
                "handler": render_study_plan_page,
            },
            "upload_materials": {
                "label": "Upload Materials",
                "hint": "Add your notes and lecture files in one place.",
                "handler": render_upload_page,
            },
            "quiz": {
                "label": "Quiz",
                "hint": "Test yourself and track your performance.",
                "handler": render_quiz_page,
            },
            "progress_dashboard": {
                "label": "Progress Dashboard",
                "hint": "View plans, uploads, and quiz analytics together.",
                "handler": render_dashboard_page,
            },
            "account": {
                "label": "Account",
                "hint": "Manage your login session.",
                "handler": render_account_page,
            },
        }
    else:
        pages = {
            "login": {
                "label": "Login",
                "hint": "Sign in with your Supabase account.",
                "handler": render_login_page,
            },
            "signup": {
                "label": "Sign up",
                "hint": "Create a new account.",
                "handler": render_signup_page,
            },
        }

    if "selected_page" not in st.session_state:
        st.session_state.selected_page = list(pages.keys())[0]
    if st.session_state.selected_page not in pages:
        st.session_state.selected_page = list(pages.keys())[0]

    nav_col_left, nav_col_center, nav_col_right = st.columns([1, 2.8, 1], gap="small")
    with nav_col_center:
        st.markdown("<div class='top-nav-title'>Navigation</div>", unsafe_allow_html=True)
        selected_page = st.segmented_control(
            "Go to",
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
        course_col, new_course_col = st.columns([1.5, 1], gap="small")
        with course_col:
            st.markdown("<div class='top-nav-title'>Active Course</div>", unsafe_allow_html=True)
            selected_course_id = st.selectbox(
                "Active course",
                options=[course["id"] for course in courses],
                index=(
                    [course["id"] for course in courses].index(active_course["id"])
                    if active_course and active_course["id"] in [course["id"] for course in courses]
                    else None
                ),
                format_func=lambda course_id: next(
                    (course["name"] for course in courses if course["id"] == course_id),
                    "Select a course",
                ),
                placeholder="Create a course to start",
                label_visibility="collapsed",
            )
            if selected_course_id and selected_course_id != st.session_state.get("active_course_id"):
                set_active_course(selected_course_id)
                st.rerun()
        with new_course_col:
            with st.form("quick_course_form", border=False):
                course_name = st.text_input(
                    "New course",
                    placeholder="New course name",
                    label_visibility="collapsed",
                )
                submitted = st.form_submit_button("Add course", use_container_width=True)
                if submitted:
                    course = add_course(course_name)
                    if course is None:
                        st.warning("Enter a course name first.")
                    else:
                        st.success(f"Active course: {course['name']}")
                        st.rerun()
    pages[selected_page]["handler"](project_root=PROJECT_ROOT)


if __name__ == "__main__":
    main()
