"""FastAPI application entrypoint for the ANKOR voice service."""

from fastapi import FastAPI

from app.api.health import router as health_router
from app.config.logging import configure_logging
from app.config.settings import get_settings

settings = get_settings()
configure_logging(settings.log_level)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(title=settings.app_name)
    application.include_router(health_router)
    return application


app = create_app()
