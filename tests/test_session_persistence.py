from __future__ import annotations

from unittest.mock import MagicMock, patch

import streamlit as st

from src.auth.session_persistence import (
    COOKIE_ACCESS,
    COOKIE_REFRESH,
    _RESTORE_FLAG,
    _decode_token,
    _encode_token,
    _set_cookie,
    bootstrap_authentication,
    clear_persisted_tokens,
    load_persisted_tokens,
    persist_tokens,
    restore_authenticated_session,
    sync_browser_auth_cookies,
)
from src.tools.state import clear_authenticated_user, set_authenticated_user


def test_encode_decode_round_trip() -> None:
    token = "eyJhbGciOiJIUzI1NiJ9.payload.signature"
    assert _decode_token(_encode_token(token)) == token


def test_decode_token_returns_none_for_corrupted_values() -> None:
    assert _decode_token("") is None
    assert _decode_token("not-valid-base64!!!") is None
    assert _decode_token("%%%") is None


def test_set_cookie_targets_parent_document() -> None:
    with patch("src.auth.session_persistence.components.html") as render_html:
        _set_cookie("rafeeqak_at", "encoded-value", 7)

    script = render_html.call_args[0][0]
    assert "window.parent" in script
    assert "doc.cookie" in script


def test_load_persisted_tokens_reads_url_encoded_cookies() -> None:
    access = _encode_token("access-token")
    refresh = _encode_token("refresh-token")
    cookies = {COOKIE_ACCESS: access.replace("=", "%3D"), COOKIE_REFRESH: refresh}

    with patch.object(st, "context", MagicMock(cookies=cookies)):
        loaded_access, loaded_refresh = load_persisted_tokens()

    assert loaded_access == "access-token"
    assert loaded_refresh == "refresh-token"


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


def test_load_persisted_tokens_returns_none_for_corrupted_cookies() -> None:
    cookies = {COOKIE_ACCESS: "bad-access", COOKIE_REFRESH: _encode_token("refresh-token")}
    with patch.object(st, "context", MagicMock(cookies=cookies)):
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
    assert set_cookie.call_args_list[0].args[1] == _encode_token("access-token")
    assert set_cookie.call_args_list[1].args[0] == COOKIE_REFRESH
    assert set_cookie.call_args_list[1].args[1] == _encode_token("refresh-token")


def test_clear_persisted_tokens_deletes_both_cookies() -> None:
    with patch("src.auth.session_persistence._delete_cookie") as delete_cookie:
        clear_persisted_tokens()

    assert delete_cookie.call_count == 2


def test_sync_browser_auth_cookies_persists_session_tokens() -> None:
    st.session_state.clear()
    st.session_state["auth_user"] = {"email": "student@example.com"}
    st.session_state["auth_access_token"] = "access-token"
    st.session_state["auth_refresh_token"] = "refresh-token"

    with patch("src.auth.session_persistence.persist_tokens") as persist:
        sync_browser_auth_cookies()

    persist.assert_called_once_with("access-token", "refresh-token")


def test_bootstrap_authentication_restores_then_syncs() -> None:
    st.session_state.clear()
    auth_service = MagicMock()
    auth_service.is_available = True

    with (
        patch("src.auth.session_persistence.restore_authenticated_session") as restore,
        patch("src.auth.session_persistence.sync_browser_auth_cookies") as sync,
    ):
        bootstrap_authentication(auth_service)

    restore.assert_called_once_with(auth_service)
    sync.assert_called_once_with()


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
    assert st.session_state.get(_RESTORE_FLAG) is True


def test_restore_authenticated_session_skips_when_already_authenticated() -> None:
    st.session_state.clear()
    set_authenticated_user(
        user={"email": "student@example.com"},
        access_token="access-token",
        refresh_token="refresh-token",
    )
    auth_service = MagicMock()
    auth_service.is_available = True

    restore_authenticated_session(auth_service)

    auth_service.restore_session.assert_not_called()


def test_restore_authenticated_session_skips_when_auth_unavailable() -> None:
    st.session_state.clear()
    auth_service = MagicMock()
    auth_service.is_available = False

    restore_authenticated_session(auth_service)

    auth_service.restore_session.assert_not_called()


def test_set_authenticated_user_persists_tokens() -> None:
    st.session_state.clear()
    user = {"email": "student@example.com"}

    with patch("src.tools.state.persist_tokens") as persist:
        set_authenticated_user(
            user=user,
            access_token="access-token",
            refresh_token="refresh-token",
        )

    persist.assert_called_once_with("access-token", "refresh-token")


def test_clear_authenticated_user_clears_persisted_cookies() -> None:
    st.session_state.clear()
    set_authenticated_user(
        user={"email": "student@example.com"},
        access_token="access-token",
        refresh_token="refresh-token",
    )

    with patch("src.tools.state.clear_persisted_tokens") as clear_cookies:
        clear_authenticated_user()

    assert st.session_state.get("auth_user") is None
    clear_cookies.assert_called_once()


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
        patch("src.tools.state.clear_persisted_tokens") as clear_cookies,
    ):
        restore_authenticated_session(auth_service)

    assert st.session_state.get("auth_user") is None
    clear_cookies.assert_called_once()
