"""Factory helpers for configuring the ANKOR Strands agent."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from app.agent.system_prompt import build_create_evaluation_system_prompt
from app.clients.ankor_backend import AnkorBackendClient
from app.tools.registry import RegisteredTool, ToolRegistry, create_tool_registry


class StrandsAgentFactory(Protocol):
    """Callable interface for creating a configured Strands agent."""

    def __call__(
        self,
        *,
        system_prompt: str,
        tools: tuple[RegisteredTool, ...],
        model: Any | None = None,
        **kwargs: Any,
    ) -> object:
        """Return a configured agent instance."""


def load_strands_agent_factory() -> StrandsAgentFactory:
    """Load the default Strands agent factory when the package is installed."""
    try:
        from strands import Agent  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "Strands is not installed. Inject `agent_factory` in tests or "
            "install the Strands package to build the real agent."
        ) from exc

    return Agent


def create_strands_agent(
    *,
    client: AnkorBackendClient | None = None,
    tool_registry: ToolRegistry | None = None,
    agent_factory: StrandsAgentFactory | None = None,
    system_prompt: str | None = None,
    system_prompt_loader: Callable[[], str] = build_create_evaluation_system_prompt,
    model: Any | None = None,
    agent_kwargs: Mapping[str, Any] | None = None,
) -> object:
    """Create a Strands agent configured with the current tool registry."""
    resolved_registry = _resolve_tool_registry(client=client, tool_registry=tool_registry)
    resolved_prompt = system_prompt or system_prompt_loader()
    resolved_factory = agent_factory or load_strands_agent_factory()

    factory_kwargs: dict[str, Any] = dict(agent_kwargs or {})
    factory_kwargs["system_prompt"] = resolved_prompt
    factory_kwargs["tools"] = resolved_registry.all()
    if model is not None:
        factory_kwargs["model"] = model

    return resolved_factory(**factory_kwargs)


def _resolve_tool_registry(
    *,
    client: AnkorBackendClient | None,
    tool_registry: ToolRegistry | None,
) -> ToolRegistry:
    """Resolve a tool registry from injected dependencies."""
    if tool_registry is not None:
        return tool_registry
    if client is None:
        raise ValueError("Either `client` or `tool_registry` must be provided.")
    return create_tool_registry(client)
