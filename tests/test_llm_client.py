from src.config import DEFAULT_GEMINI_MODEL
from src.tools.llm_client import get_llm_settings


def test_llm_settings_prefers_gemini_key(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    settings = get_llm_settings()

    assert settings.provider == "gemini"
    assert settings.api_key == "gemini-test-key"
    assert settings.model == "gemini-test-model"
    assert settings.is_configured is True


def test_llm_settings_reads_gemini_config_from_env_file(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "GEMINI_API_KEY=gemini-file-key\nGEMINI_MODEL=gemini-file-model\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    settings = get_llm_settings(env_path=env_path, override_env=True)

    assert settings.api_key == "gemini-file-key"
    assert settings.model == "gemini-file-model"
    assert settings.is_configured is True


def test_llm_settings_defaults_gemini_model_when_missing(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("GEMINI_API_KEY=gemini-test-key\n", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)

    settings = get_llm_settings(env_path=env_path, override_env=True)

    assert settings.model == DEFAULT_GEMINI_MODEL


def test_llm_settings_is_unconfigured_when_gemini_is_placeholder(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "your_gemini_api_key_here")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-test-model")

    settings = get_llm_settings()

    assert settings.provider == "gemini"
    assert settings.model == "gemini-test-model"
    assert settings.is_configured is False
