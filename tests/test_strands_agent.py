from unittest.mock import MagicMock, sentinel

from app.agent.strands_agent import create_strands_agent
from app.agent.system_prompt import build_create_evaluation_system_prompt
from app.clients.ankor_backend import AnkorBackendClient
from app.tools.registry import ToolRegistry, create_tool_registry


def test_create_strands_agent_registers_all_tools() -> None:
    client = MagicMock(spec=AnkorBackendClient)

    agent = create_strands_agent(
        client=client,
        system_prompt="Coach-facing prompt",
        agent_factory=lambda **kwargs: kwargs,
    )

    assert [tool.name for tool in agent["tools"]] == [
        "find_athlete",
        "list_evaluation_templates",
        "create_evaluation_draft",
        "finalize_evaluation",
    ]
    assert agent["system_prompt"] == "Coach-facing prompt"


def test_create_strands_agent_loads_default_system_prompt() -> None:
    registry = create_tool_registry(MagicMock(spec=AnkorBackendClient))

    agent = create_strands_agent(
        tool_registry=registry,
        agent_factory=lambda **kwargs: kwargs,
    )

    assert agent["system_prompt"] == build_create_evaluation_system_prompt()


def test_create_strands_agent_supports_mocked_dependencies() -> None:
    registry = MagicMock(spec=ToolRegistry)
    registry.all.return_value = tuple()
    system_prompt_loader = MagicMock(return_value="Injected prompt")
    agent_factory = MagicMock(return_value=sentinel.agent_instance)
    model = object()

    agent = create_strands_agent(
        tool_registry=registry,
        system_prompt_loader=system_prompt_loader,
        agent_factory=agent_factory,
        model=model,
        agent_kwargs={"runtime": "test"},
    )

    assert agent is sentinel.agent_instance
    registry.all.assert_called_once_with()
    system_prompt_loader.assert_called_once_with()
    agent_factory.assert_called_once_with(
        system_prompt="Injected prompt",
        tools=tuple(),
        model=model,
        runtime="test",
    )
