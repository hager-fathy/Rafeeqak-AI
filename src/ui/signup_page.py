from pathlib import Path

import streamlit as st

from src.auth import AuthService
from src.tools.state import set_authenticated_user
from src.ui.theme import render_page_hero


def render_signup_page(project_root: Path) -> None:
    del project_root

    render_page_hero(
        "Create Account",
        "Sign up once to save your study memory and continue from any session.",
        chips=["Personal profile", "Cloud memory"],
        accent_chip="Sign up",
    )

    auth_service = AuthService()
    if not auth_service.is_available:
        st.error(f"Authentication is not configured: {auth_service.unavailability_reason}")
        return

    left_col, form_col, right_col = st.columns([1, 1.4, 1], gap="small")
    with form_col:
        with st.container(border=True):
            st.markdown("#### New account")
            with st.form("signup_form"):
                full_name = st.text_input("Full name", placeholder="Demo Student")
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm password", type="password")
                submit = st.form_submit_button("Create account", type="primary", width="stretch")

            if submit:
                if not email.strip() or not password:
                    st.warning("Email and password are required.")
                    return
                if password != confirm_password:
                    st.warning("Passwords do not match.")
                    return
                if len(password) < 8:
                    st.warning("Password must be at least 8 characters.")
                    return

                result = auth_service.sign_up(
                    email=email.strip(),
                    password=password,
                    full_name=full_name.strip(),
                )
                if not result["ok"]:
                    st.error(result["message"])
                    return

                if result["requires_email_confirmation"]:
                    st.success("Account created. Please verify your email, then login.")
                    return

                set_authenticated_user(
                    user=result["user"],
                    access_token=result["access_token"],
                    refresh_token=result["refresh_token"],
                )
                st.success("Account created and logged in.")
                st.rerun()
