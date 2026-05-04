from src.auth import AuthService


def test_auth_service_status_shape() -> None:
    service = AuthService()
    assert isinstance(service.is_available, bool)
    assert isinstance(service.unavailability_reason, str)
