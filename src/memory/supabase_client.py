from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv

try:
    from supabase import Client, create_client
except ModuleNotFoundError:  # pragma: no cover - handled by runtime checks
    Client = Any  # type: ignore[misc,assignment]
    create_client = None  # type: ignore[assignment]


load_dotenv()


@dataclass(frozen=True)
class SupabaseSettings:
    url: str | None
    key: str | None
    default_student_email: str
    default_student_name: str

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.key)


def get_supabase_settings() -> SupabaseSettings:
    return SupabaseSettings(
        url=os.getenv("SUPABASE_URL"),
        key=os.getenv("SUPABASE_KEY"),
        default_student_email=os.getenv("SUPABASE_DEFAULT_STUDENT_EMAIL", "student@example.com"),
        default_student_name=os.getenv("SUPABASE_DEFAULT_STUDENT_NAME", "Demo Student"),
    )


@lru_cache(maxsize=1)
def get_supabase_client() -> Client | None:
    settings = get_supabase_settings()
    if not settings.is_configured or create_client is None:
        return None
    return create_client(settings.url, settings.key)
