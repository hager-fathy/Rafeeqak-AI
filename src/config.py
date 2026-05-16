from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite-preview"

_LOADED_ENV_PATHS: set[Path] = set()


def project_env_path() -> Path:
    return PROJECT_ROOT / ".env"


def load_project_env(*, env_path: Path | str | None = None, override: bool = False) -> bool:
    resolved_path = Path(env_path).resolve() if env_path is not None else project_env_path().resolve()
    if not resolved_path.exists():
        return False
    if resolved_path in _LOADED_ENV_PATHS and not override:
        return True

    loaded = load_dotenv(dotenv_path=resolved_path, override=override)
    _LOADED_ENV_PATHS.add(resolved_path)
    return loaded
