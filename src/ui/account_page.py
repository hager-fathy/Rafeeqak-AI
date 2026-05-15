from pathlib import Path

import streamlit as st

from src.auth import AuthService
from src.tools.state import clear_authenticated_user, get_authenticated_user
from src.ui.theme import render_page_hero


def render_account_page(project_root: Path) -> None:
    del project_root

    user = get_authenticated_user()
    if not user:
        st.info("No active user session.")
        return

    email = user.get("email", "Unknown")
    full_name = user.get("user_metadata", {}).get("full_name") or user.get("email", "User")

    render_page_hero(
        "Account",
        "Manage your active session.",
        chips=[f"User: {full_name}", f"Email: {email}"],
        accent_chip="Session",
    )

    with st.container(border=True):
        st.markdown("#### Session details")
        st.write(f"Signed in as: `{email}`")

        if st.button("Logout", type="primary", use_container_width=True):
            result = AuthService().sign_out()
            clear_authenticated_user()
            if result["ok"]:
                st.success("Logged out.")
            else:
                st.warning(result["message"])
            st.rerun()
