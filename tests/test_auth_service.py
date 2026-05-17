from src.auth import AuthService
from src.auth.service import build_local_demo_user
from src.memory import supabase_client


def test_auth_service_status_shape() -> None:
    service = AuthService()
    assert isinstance(service.is_available, bool)
    assert isinstance(service.unavailability_reason, str)


def test_supabase_client_ignores_broken_env_proxy_by_default(monkeypatch) -> None:
    captured = {}

    def fake_create_client(url, key, options=None):
        captured["url"] = url
        captured["key"] = key
        captured["options"] = options
        return object()

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "test-key")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")
    monkeypatch.delenv("SUPABASE_TRUST_ENV_PROXY", raising=False)
    monkeypatch.setattr(supabase_client, "create_client", fake_create_client)
    supabase_client.get_supabase_client.cache_clear()

    client = supabase_client.get_supabase_client()

    assert client is not None
    assert captured["url"] == "https://example.supabase.co"
    assert captured["key"] == "test-key"
    assert captured["options"].httpx_client._trust_env is False

    supabase_client.get_supabase_client.cache_clear()


def test_build_local_demo_user_normalizes_identity() -> None:
    user = build_local_demo_user(email=" Demo@Example.com ", full_name="Demo Student")

    assert user["email"] == "demo@example.com"
    assert user["user_metadata"]["full_name"] == "Demo Student"
    assert user["user_metadata"]["auth_provider"] == "local_demo"
    assert user["app_metadata"]["provider"] == "local_demo"
