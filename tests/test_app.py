from fastapi import status
from fastapi.testclient import TestClient

from app.api.deps import AppServices
from app.main import create_app
from app.utils.errors import AppError


def test_app_startup_initializes_shared_services() -> None:
    application = create_app()

    with TestClient(application) as client:
        services = client.app.state.services

        assert isinstance(services, AppServices)
        assert services.settings.app_name == application.title


def test_app_error_handler_returns_json_response() -> None:
    application = create_app()

    @application.get("/error")
    async def error_route() -> None:
        raise AppError(
            "Service unavailable",
            error_code="service_unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    with TestClient(application) as client:
        response = client.get("/error")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "error": "service_unavailable",
        "message": "Service unavailable",
    }
