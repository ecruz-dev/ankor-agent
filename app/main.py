"""FastAPI application entrypoint for the ANKOR voice service."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.deps import create_app_services
from app.api.health import router as health_router
from app.config.logging import configure_logging
from app.config.settings import get_settings
from app.utils.errors import AppError, app_error_handler

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Initialize and clean up application-scoped services."""
    application.state.services = create_app_services(settings)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    application.add_exception_handler(AppError, app_error_handler)
    application.include_router(health_router)
    return application


app = create_app()
