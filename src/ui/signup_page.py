from pathlib import Path

import streamlit as st

from src.auth import AuthService, build_local_demo_user, rerun_after_auth_state_change
from src.localization import t
from src.tools.state import get_selected_language, set_authenticated_user
from src.ui.theme import render_page_hero


def render_signup_page(project_root: Path) -> None:
    del project_root
    language = get_selected_language()

    render_page_hero(
        t("signup.title", language),
        t("signup.subtitle", language),
        chips=[t("signup.chip.profile", language), t("signup.chip.memory", language)],
        accent_chip=t("signup.accent", language),
        language=language,
    )

    auth_service = AuthService()
    if not auth_service.is_available:
        st.info(t("auth.demo_mode_info", language, reason=auth_service.unavailability_reason))
        left_col, form_col, right_col = st.columns([1, 1.4, 1], gap="small", vertical_alignment="center")
        with form_col:
            with st.container(border=True):
                st.markdown(f"#### {t('auth.demo_mode_title', language)}")
                with st.form("demo_signup_form"):
                    full_name = st.text_input(
                        t("signup.full_name", language),
                        placeholder=t("signup.full_name_placeholder", language),
                    )
                    email = st.text_input(
                        t("signup.email", language),
                        value="demo@example.com",
                        placeholder=t("login.email_placeholder", language),
                    )
                    submit = st.form_submit_button(
                        t("auth.demo_mode_continue", language),
                        type="primary",
                        use_container_width=True,
                    )
                if submit:
                    user = build_local_demo_user(email=email, full_name=full_name)
                    set_authenticated_user(user=user, access_token=None, refresh_token=None)
                    st.success(t("auth.demo_mode_success", language))
                    rerun_after_auth_state_change()
        return

    left_col, form_col, right_col = st.columns([1, 1.4, 1], gap="small", vertical_alignment="center")
    with form_col:
        with st.container(border=True):
            st.markdown(f"#### {t('signup.form_title', language)}")
            with st.form("signup_form"):
                full_name = st.text_input(
                    t("signup.full_name", language),
                    placeholder=t("signup.full_name_placeholder", language),
                )
                email = st.text_input(t("signup.email", language), placeholder=t("login.email_placeholder", language))
                password = st.text_input(t("signup.password", language), type="password")
                confirm_password = st.text_input(t("signup.confirm_password", language), type="password")
                submit = st.form_submit_button(t("signup.submit", language), type="primary", use_container_width=True)

            if submit:
                if not email.strip() or not password:
                    st.warning(t("signup.required", language))
                    return
                if password != confirm_password:
                    st.warning(t("signup.password_mismatch", language))
                    return
                if len(password) < 8:
                    st.warning(t("signup.password_short", language))
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
                    st.success(t("signup.verify_email", language))
                    return

                set_authenticated_user(
                    user=result["user"],
                    access_token=result["access_token"],
                    refresh_token=result["refresh_token"],
                )
                st.success(t("signup.success", language))
                rerun_after_auth_state_change()
