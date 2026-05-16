from __future__ import annotations

from unittest.mock import MagicMock, patch

import streamlit as st

from src.auth.session_persistence import (
    COOKIE_ACCESS,
    COOKIE_REFRESH,
    _decode_token,
    _encode_token,
    clear_persisted_tokens,
    load_persisted_tokens,
    persist_tokens,
    restore_authenticated_session,
)


def test_encode_decode_round_trip() -> None:
    token = "eyJhbGciOiJIUzI1NiJ9.payload.signature"
    assert _decode_token(_encode_token(token)) == token


def test_load_persisted_tokens_reads_cookies() -> None:
    access = _encode_token("access-token")
    refresh = _encode_token("refresh-token")
    cookies = {COOKIE_ACCESS: access, COOKIE_REFRESH: refresh}

    with patch.object(st, "context", MagicMock(cookies=cookies)):
        loaded_access, loaded_refresh = load_persisted_tokens()

    assert loaded_access == "access-token"
    assert loaded_refresh == "refresh-token"


def test_load_persisted_tokens_returns_none_when_missing() -> None:
    with patch.object(st, "context", MagicMock(cookies={})):
        assert load_persisted_tokens() == (None, None)


def test_load_persisted_tokens_handles_cookie_errors() -> None:
    broken_context = MagicMock()
    broken_context.cookies.get.side_effect = RuntimeError("blocked")

    with patch.object(st, "context", broken_context):
        assert load_persisted_tokens() == (None, None)


def test_persist_tokens_skips_empty_values() -> None:
    with patch("src.auth.session_persistence._set_cookie") as set_cookie:
        persist_tokens(None, "refresh")
        persist_tokens("access", None)
        set_cookie.assert_not_called()


def test_persist_tokens_writes_both_cookies() -> None:
    with patch("src.auth.session_persistence._set_cookie") as set_cookie:
        persist_tokens("access-token", "refresh-token")

    assert set_cookie.call_count == 2
    assert set_cookie.call_args_list[0].args[0] == COOKIE_ACCESS
    assert set_cookie.call_args_list[1].args[0] == COOKIE_REFRESH


def test_clear_persisted_tokens_deletes_both_cookies() -> None:
    with patch("src.auth.session_persistence._delete_cookie") as delete_cookie:
        clear_persisted_tokens()

    assert delete_cookie.call_count == 2


def test_restore_authenticated_session_restores_from_cookies() -> None:
    st.session_state.clear()
    auth_service = MagicMock()
    auth_service.is_available = True
    auth_service.restore_session.return_value = {
        "ok": True,
        "user": {"email": "student@example.com"},
    }

    cookies = {
        COOKIE_ACCESS: _encode_token("access-token"),
        COOKIE_REFRESH: _encode_token("refresh-token"),
    }

    with patch.object(st, "context", MagicMock(cookies=cookies)):
        restore_authenticated_session(auth_service)

    assert st.session_state["auth_user"]["email"] == "student@example.com"
    assert st.session_state["auth_access_token"] == "access-token"
    auth_service.restore_session.assert_called_once_with(
        access_token="access-token",
        refresh_token="refresh-token",
    )


def test_restore_authenticated_session_runs_once_per_connection() -> None:
    st.session_state.clear()
    auth_service = MagicMock()
    auth_service.is_available = True

    with patch.object(st, "context", MagicMock(cookies={})):
        restore_authenticated_session(auth_service)
        restore_authenticated_session(auth_service)

    auth_service.restore_session.assert_not_called()


def test_restore_authenticated_session_clears_invalid_cookies() -> None:
    st.session_state.clear()
    auth_service = MagicMock()
    auth_service.is_available = True
    auth_service.restore_session.return_value = {"ok": False, "message": "expired"}

    cookies = {
        COOKIE_ACCESS: _encode_token("access-token"),
        COOKIE_REFRESH: _encode_token("refresh-token"),
    }

    with (
        patch.object(st, "context", MagicMock(cookies=cookies)),
        patch("src.auth.session_persistence.clear_persisted_tokens") as clear_cookies,
    ):
        restore_authenticated_session(auth_service)

    assert st.session_state.get("auth_user") is None
    clear_cookies.assert_called_once()
