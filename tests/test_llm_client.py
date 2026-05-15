from src.tools.llm_client import get_llm_settings


def test_llm_settings_prefers_gemini_key(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    settings = get_llm_settings()

    assert settings.provider == "gemini"
    assert settings.api_key == "gemini-test-key"
    assert settings.model == "gemini-test-model"
    assert settings.is_configured is True


def test_llm_settings_is_unconfigured_when_gemini_is_placeholder(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    settings = get_llm_settings()

    assert settings.provider == "gemini"
    assert settings.model == "gemini-test-model"
    assert settings.is_configured is False
