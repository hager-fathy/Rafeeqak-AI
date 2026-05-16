from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

try:
    import httpx
    from supabase import Client, ClientOptions, create_client
except (ImportError, ModuleNotFoundError):  # pragma: no cover - handled by runtime checks
    Client = Any  # type: ignore[misc,assignment]
    create_client = None  # type: ignore[assignment]
    import httpx

    class ClientOptions:  # type: ignore[override]
        def __init__(self, *, httpx_client: Any) -> None:
            self.httpx_client = httpx_client


load_dotenv()


PLACEHOLDER_VALUES = {"", "replace_me", "your_supabase_project_url", "your_supabase_publishable_key"}


@dataclass(frozen=True)
class SupabaseSettings:
    url: str | None
    key: str | None
    default_student_email: str
    default_student_name: str
    trust_env_proxy: bool

    @property
    def is_configured(self) -> bool:
        return bool(
            self.url
            and self.key
            and self.url.strip() not in PLACEHOLDER_VALUES
            and self.key.strip() not in PLACEHOLDER_VALUES
        )


def get_supabase_settings() -> SupabaseSettings:
    return SupabaseSettings(
        url=os.getenv("SUPABASE_URL"),
        key=os.getenv("SUPABASE_KEY"),
        default_student_email=os.getenv("SUPABASE_DEFAULT_STUDENT_EMAIL", "student@example.com"),
        default_student_name=os.getenv("SUPABASE_DEFAULT_STUDENT_NAME", "Demo Student"),
        trust_env_proxy=os.getenv("SUPABASE_TRUST_ENV_PROXY", "").strip().lower()
        in {"1", "true", "yes", "on"},
    )


@lru_cache(maxsize=1)
def get_supabase_client() -> Client | None:
    settings = get_supabase_settings()
    if not settings.is_configured or create_client is None:
        return None

    options = None
    if ClientOptions is not None and httpx is not None:
        options = ClientOptions(
            httpx_client=httpx.Client(trust_env=settings.trust_env_proxy)
        )

    return create_client(settings.url, settings.key, options)
