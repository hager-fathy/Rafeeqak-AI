from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

try:
    from google import genai
    from google.genai import types as genai_types
except (ImportError, ModuleNotFoundError):  # pragma: no cover - optional runtime dependency guard
    genai = None  # type: ignore[assignment]
    genai_types = None  # type: ignore[assignment]


load_dotenv()


PLACEHOLDER_KEYS = {"", "your_gemini_api_key_here", "replace_me"}


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    api_key: str | None
    model: str

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip() not in PLACEHOLDER_KEYS)


def get_llm_settings() -> LLMSettings:
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    return LLMSettings(
        provider="gemini",
        api_key=gemini_key,
        model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    )


class LLMClient:
    """Small optional LLM wrapper with deterministic fallbacks handled by callers."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.settings = settings or get_llm_settings()
        self.client = self._build_client()

    @property
    def is_available(self) -> bool:
        return self.settings.is_configured and genai is not None

    def _build_client(self) -> Any | None:
        if not self.is_available:
            return None
        return genai.Client(api_key=self.settings.api_key)

    def generate_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 700,
    ) -> str | None:
        if self.client is None:
            return None

        return self._generate_gemini_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _generate_gemini_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> str | None:
        if genai_types is None:
            return None

        response = self.client.models.generate_content(
            model=self.settings.model,
            contents=user_prompt,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )
        content = getattr(response, "text", None)
        return content.strip() if content else None

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.4,
        max_tokens: int = 1200,
    ) -> dict[str, Any] | None:
        text = self.generate_text(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if not text:
            return None

        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
