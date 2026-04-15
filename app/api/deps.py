"""Shared application dependencies exposed through FastAPI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request

from app.config.settings import Settings, get_settings


@dataclass(slots=True, frozen=True)
class AppServices:
    """Application-scoped services shared across request handlers."""

    settings: Settings


def create_app_services(settings: Settings | None = None) -> AppServices:
    """Build the shared service container for the application."""
    return AppServices(settings=settings or get_settings())


def get_app_services(request: Request) -> AppServices:
    """Return the shared service container stored on the FastAPI app."""
    return cast(AppServices, request.app.state.services)


def get_app_settings(
    services: Annotated[AppServices, Depends(get_app_services)],
) -> Settings:
    """Expose application settings through the shared dependency container."""
    return services.settings
