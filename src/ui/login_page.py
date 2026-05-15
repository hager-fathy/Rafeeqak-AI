from pathlib import Path

import streamlit as st

from src.auth import AuthService
from src.localization import t
from src.tools.state import get_selected_language, set_authenticated_user
from src.ui.theme import render_page_hero


def render_login_page(project_root: Path) -> None:
    del project_root
    language = get_selected_language()

    render_page_hero(
        t("login.title", language),
        t("login.subtitle", language),
        chips=[t("login.chip.secure", language), t("login.chip.auth", language)],
        accent_chip=t("login.accent", language),
        language=language,
    )

    auth_service = AuthService()
    if not auth_service.is_available:
        st.error(t("auth.not_configured", language, reason=auth_service.unavailability_reason))
        return

    center_col, form_col, right_col = st.columns([1, 1.4, 1], gap="small")
    with form_col:
        with st.container(border=True):
            st.markdown(f"#### {t('login.form_title', language)}")
            with st.form("login_form"):
                email = st.text_input(t("login.email", language), placeholder=t("login.email_placeholder", language))
                password = st.text_input(t("login.password", language), type="password")
                submit = st.form_submit_button(t("login.submit", language), type="primary", use_container_width=True)

            if submit:
                if not email.strip() or not password:
                    st.warning(t("login.required", language))
                else:
                    result = auth_service.sign_in(email=email.strip(), password=password)
                    if result["ok"]:
                        set_authenticated_user(
                            user=result["user"],
                            access_token=result["access_token"],
                            refresh_token=result["refresh_token"],
                        )
                        st.success(t("login.success", language))
                        st.rerun()
                    else:
                        st.error(result["message"])
