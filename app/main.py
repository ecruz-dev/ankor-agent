"""FastAPI application entrypoint for the ANKOR voice service."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import AppServices, create_app_services
from app.api.health import router as health_router
from app.api.session import router as session_router
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.utils.errors import AppError, app_error_handler

settings = get_settings()
configure_logging(settings.log_level)


def create_lifespan(
    services: AppServices | None = None,
) -> Callable[[FastAPI], AsyncIterator[None]]:
    """Create the FastAPI lifespan handler for application services."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        """Initialize and clean up application-scoped services."""
        app_services = services or create_app_services(settings)
        application.state.services = app_services
        try:
            yield
        finally:
            await app_services.aclose()

    return lifespan


def create_app(*, services: AppServices | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.app_name,
        lifespan=create_lifespan(services),
    )
    application.add_exception_handler(AppError, app_error_handler)
    application.include_router(health_router)
    application.include_router(session_router)
    return application


app = create_app()
