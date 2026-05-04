from __future__ import annotations

from typing import Any

from supabase_auth.errors import AuthApiError, AuthError, AuthWeakPasswordError

from src.memory.supabase_client import get_supabase_client, get_supabase_settings


class AuthService:
    def __init__(self) -> None:
        self.client = get_supabase_client()
        self.settings = get_supabase_settings()

    @property
    def is_available(self) -> bool:
        return self.client is not None and self.settings.is_configured

    @property
    def unavailability_reason(self) -> str:
        if not self.settings.is_configured:
            return "SUPABASE_URL or SUPABASE_KEY is missing."
        if self.client is None:
            return "Supabase client is not available."
        return ""

    def sign_up(self, *, email: str, password: str, full_name: str) -> dict[str, Any]:
        if not self.is_available:
            return {"ok": False, "message": self.unavailability_reason}

        payload: dict[str, Any] = {
            "email": email,
            "password": password,
        }
        if full_name.strip():
            payload["options"] = {"data": {"full_name": full_name.strip()}}

        try:
            response = self.client.auth.sign_up(payload)
            user_data = response.user.model_dump() if response.user else None
            session = response.session
            return {
                "ok": True,
                "message": "Sign up successful.",
                "user": user_data,
                "access_token": session.access_token if session else None,
                "refresh_token": session.refresh_token if session else None,
                "requires_email_confirmation": session is None,
            }
        except AuthWeakPasswordError as exc:
            return {"ok": False, "message": f"Weak password: {exc}"}
        except AuthApiError as exc:
            return {"ok": False, "message": str(exc)}
        except AuthError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:  # pragma: no cover - external client behavior
            return {"ok": False, "message": f"Sign up failed: {exc}"}

    def sign_in(self, *, email: str, password: str) -> dict[str, Any]:
        if not self.is_available:
            return {"ok": False, "message": self.unavailability_reason}

        try:
            response = self.client.auth.sign_in_with_password(
                {
                    "email": email,
                    "password": password,
                }
            )
            if not response.user or not response.session:
                return {"ok": False, "message": "Login did not return an active session."}

            return {
                "ok": True,
                "message": "Login successful.",
                "user": response.user.model_dump(),
                "access_token": response.session.access_token,
                "refresh_token": response.session.refresh_token,
            }
        except AuthApiError as exc:
            return {"ok": False, "message": str(exc)}
        except AuthError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:  # pragma: no cover - external client behavior
            return {"ok": False, "message": f"Login failed: {exc}"}

    def restore_session(self, *, access_token: str, refresh_token: str) -> dict[str, Any]:
        if not self.is_available:
            return {"ok": False, "message": self.unavailability_reason}

        try:
            response = self.client.auth.set_session(access_token, refresh_token)
            user_data = response.user.model_dump() if response.user else None
            return {"ok": True, "user": user_data}
        except AuthApiError as exc:
            return {"ok": False, "message": str(exc)}
        except AuthError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:  # pragma: no cover - external client behavior
            return {"ok": False, "message": f"Session restore failed: {exc}"}

    def sign_out(self) -> dict[str, Any]:
        if not self.is_available:
            return {"ok": False, "message": self.unavailability_reason}

        try:
            self.client.auth.sign_out()
            return {"ok": True, "message": "Logged out."}
        except AuthApiError as exc:
            return {"ok": False, "message": str(exc)}
        except AuthError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception as exc:  # pragma: no cover - external client behavior
            return {"ok": False, "message": f"Logout failed: {exc}"}
