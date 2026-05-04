from pathlib import Path

import streamlit as st

from src.auth import AuthService
from src.tools.state import set_authenticated_user
from src.ui.theme import render_page_hero


def render_login_page(project_root: Path) -> None:
    del project_root

    render_page_hero(
        "Login",
        "Sign in to access your saved plans, quiz history, and personalized memory.",
        chips=["Secure access", "Supabase Auth"],
        accent_chip="Sign in",
    )

    auth_service = AuthService()
    if not auth_service.is_available:
        st.error(f"Authentication is not configured: {auth_service.unavailability_reason}")
        return

    center_col, form_col, right_col = st.columns([1, 1.4, 1], gap="small")
    with form_col:
        with st.container(border=True):
            st.markdown("#### Account login")
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login", type="primary", width="stretch")

            if submit:
                if not email.strip() or not password:
                    st.warning("Email and password are required.")
                else:
                    result = auth_service.sign_in(email=email.strip(), password=password)
                    if result["ok"]:
                        set_authenticated_user(
                            user=result["user"],
                            access_token=result["access_token"],
                            refresh_token=result["refresh_token"],
                        )
                        st.success("Login successful.")
                        st.rerun()
                    else:
                        st.error(result["message"])
