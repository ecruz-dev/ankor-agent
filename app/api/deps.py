"""Shared application dependencies exposed through FastAPI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, Request

from app.agent.strands_agent import create_strands_agent
from app.clients.ankor_backend import AnkorBackendClient
from app.config.settings import Settings, get_settings
from app.memory.agentcore_memory import AgentCoreMemorySessionStore
from app.services.conversation_service import ConversationService
from app.services.tool_executor import ToolExecutor
from app.tools.registry import create_tool_registry
from app.utils.errors import AppError


@dataclass(slots=True, frozen=True)
class AppServices:
    """Application-scoped services shared across request handlers."""

    settings: Settings
    conversation_service: ConversationService | None = None
    backend_client: AnkorBackendClient | None = None

    async def aclose(self) -> None:
        """Release owned service resources."""
        if self.backend_client is not None:
            await self.backend_client.aclose()


def create_app_services(settings: Settings | None = None) -> AppServices:
    """Build the shared service container for the application."""
    resolved_settings = settings or get_settings()
    backend_client = AnkorBackendClient.from_settings(resolved_settings)

    try:
        tool_registry = create_tool_registry(backend_client)
        agent = create_strands_agent(tool_registry=tool_registry)
        conversation_service: ConversationService | None = ConversationService(
            agent=agent,
            session_store=AgentCoreMemorySessionStore(),
            tool_executor=ToolExecutor(tool_registry=tool_registry),
        )
    except RuntimeError:
        conversation_service = None

    return AppServices(
        settings=resolved_settings,
        conversation_service=conversation_service,
        backend_client=backend_client,
    )


def get_app_services(request: Request) -> AppServices:
    """Return the shared service container stored on the FastAPI app."""
    return cast(AppServices, request.app.state.services)


def get_app_settings(
    services: Annotated[AppServices, Depends(get_app_services)],
) -> Settings:
    """Expose application settings through the shared dependency container."""
    return services.settings


def get_conversation_service(
    services: Annotated[AppServices, Depends(get_app_services)],
) -> ConversationService:
    """Return the configured conversation service for API handlers."""
    if services.conversation_service is None:
        raise AppError(
            (
                "Conversation service is not configured. Install Strands and "
                "configure the agent dependencies before using this endpoint."
            ),
            error_code="conversation_service_unavailable",
            status_code=503,
        )
    return services.conversation_service
