"""Browser-side persistence for Supabase auth tokens across page refreshes."""

from __future__ import annotations

import base64
import json
from typing import TYPE_CHECKING

import streamlit as st
import streamlit.components.v1 as components

if TYPE_CHECKING:
    from src.auth.service import AuthService

COOKIE_ACCESS = "rafeeqak_at"
COOKIE_REFRESH = "rafeeqak_rt"
COOKIE_MAX_AGE_DAYS = 7
_RESTORE_FLAG = "_auth_restore_attempted"


def load_persisted_tokens() -> tuple[str | None, str | None]:
    """Load access and refresh tokens from browser cookies."""
    try:
        cookies = st.context.cookies
        access_raw = cookies.get(COOKIE_ACCESS)
        refresh_raw = cookies.get(COOKIE_REFRESH)
    except Exception:
        return None, None

    if not access_raw or not refresh_raw:
        return None, None

    access_token = _decode_token(str(access_raw))
    refresh_token = _decode_token(str(refresh_raw))
    if not access_token or not refresh_token:
        return None, None
    return access_token, refresh_token


def persist_tokens(access_token: str | None, refresh_token: str | None) -> None:
    """Write auth tokens to browser cookies (no-op if either token is missing)."""
    if not access_token or not refresh_token:
        return
    try:
        _set_cookie(COOKIE_ACCESS, _encode_token(access_token), COOKIE_MAX_AGE_DAYS)
        _set_cookie(COOKIE_REFRESH, _encode_token(refresh_token), COOKIE_MAX_AGE_DAYS)
    except Exception:
        return


def clear_persisted_tokens() -> None:
    """Remove persisted auth cookies from the browser."""
    try:
        _delete_cookie(COOKIE_ACCESS)
        _delete_cookie(COOKIE_REFRESH)
    except Exception:
        return


def restore_authenticated_session(auth_service: AuthService) -> None:
    """Restore Supabase session from cookies or in-memory tokens once per connection."""
    if st.session_state.get(_RESTORE_FLAG):
        return
    st.session_state[_RESTORE_FLAG] = True

    from src.tools.state import (
        clear_authenticated_user,
        is_authenticated,
        set_authenticated_user,
    )

    if not auth_service.is_available or is_authenticated():
        return

    access_token, refresh_token = load_persisted_tokens()
    if not access_token or not refresh_token:
        access_token = st.session_state.get("auth_access_token")
        refresh_token = st.session_state.get("auth_refresh_token")

    if not access_token or not refresh_token:
        return

    restored = auth_service.restore_session(
        access_token=access_token,
        refresh_token=refresh_token,
    )
    if restored.get("ok") and restored.get("user"):
        set_authenticated_user(
            user=restored["user"],
            access_token=access_token,
            refresh_token=refresh_token,
        )
        return

    clear_authenticated_user()
    clear_persisted_tokens()


def _encode_token(token: str) -> str:
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii")


def _decode_token(encoded: str) -> str | None:
    if not encoded:
        return None
    try:
        return base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return encoded


def _cookie_attributes() -> str:
    try:
        host = str(st.context.headers.get("Host") or "").lower()
        if host and "localhost" not in host and "127.0.0.1" not in host:
            return "; path=/; SameSite=Lax; Secure"
    except Exception:
        pass
    return "; path=/; SameSite=Lax"


def _set_cookie(name: str, value: str, max_age_days: int) -> None:
    flags = _cookie_attributes()
    name_js = json.dumps(name)
    value_js = json.dumps(value)
    components.html(
        f"""
        <script>
        (function() {{
            var name = {name_js};
            var value = {value_js};
            var days = {max_age_days};
            var expires = "";
            if (days) {{
                var date = new Date();
                date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
                expires = "; expires=" + date.toUTCString();
            }}
            document.cookie = name + "=" + encodeURIComponent(value) + expires + {json.dumps(flags)};
        }})();
        </script>
        """,
        height=0,
        width=0,
    )


def _delete_cookie(name: str) -> None:
    flags = _cookie_attributes()
    name_js = json.dumps(name)
    components.html(
        f"""
        <script>
        (function() {{
            var name = {name_js};
            document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:00 GMT" + {json.dumps(flags)};
        }})();
        </script>
        """,
        height=0,
        width=0,
    )
