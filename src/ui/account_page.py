from pathlib import Path

import streamlit as st

from src.auth import AuthService
from src.localization import t
from src.tools.state import clear_authenticated_user, get_authenticated_user, get_selected_language
from src.ui.theme import render_page_hero


def render_account_page(project_root: Path) -> None:
    del project_root
    language = get_selected_language()

    user = get_authenticated_user()
    if not user:
        st.info(t("account.no_session", language))
        return

    email = user.get("email", "Unknown")
    full_name = user.get("user_metadata", {}).get("full_name") or user.get("email", t("common.user", language))

    render_page_hero(
        t("account.title", language),
        t("account.subtitle", language),
        chips=[
            f"{t('common.user', language)}: {full_name}",
            f"{t('common.email', language)}: {email}",
        ],
        accent_chip=t("account.accent", language),
        language=language,
    )

    with st.container(border=True):
        st.markdown(f"#### {t('account.details', language)}")
        st.write(t("account.signed_in_as", language, email=email))

        if st.button(t("account.logout", language), type="primary", use_container_width=True):
            auth_service = AuthService()
            provider = (user.get("app_metadata") or {}).get("provider") or (user.get("user_metadata") or {}).get("auth_provider")
            if provider == "local_demo" or not auth_service.is_available:
                result = {"ok": True, "message": t("account.logged_out", language)}
            else:
                result = auth_service.sign_out()
            clear_authenticated_user()
            if result["ok"]:
                st.success(t("account.logged_out", language))
            else:
                st.warning(result["message"])
            st.rerun()
