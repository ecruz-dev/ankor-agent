import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.clients.ankor_backend import (
    AnkorBackendClient,
    EvaluationTemplateListResponse,
    EvaluationTemplateSummary,
    FinalizeEvaluationResponse,
)
from app.schemas.athlete import AthleteLookupRequest, AthleteLookupResponse, AthleteMatch
from app.schemas.evaluation import (
    EvaluationDraft,
    EvaluationDraftRequest,
    EvaluationDraftResponse,
)
from app.schemas.session import ResolutionStatus
from app.tools.create_evaluation_draft import CreateEvaluationDraftTool
from app.tools.finalize_evaluation import (
    FinalizeEvaluationInput,
    FinalizeEvaluationTool,
)
from app.tools.find_athlete import FindAthleteTool
from app.tools.list_evaluation_templates import (
    ListEvaluationTemplatesInput,
    ListEvaluationTemplatesTool,
)
from app.tools.registry import create_tool_registry, get_tool_map


def test_find_athlete_tool_calls_backend_client() -> None:
    async def run_test() -> None:
        expected = AthleteLookupResponse(
            query="Jane Doe",
            status=ResolutionStatus.RESOLVED,
            selected_athlete=AthleteMatch(
                athlete_id="athlete-1",
                full_name="Jane Doe",
                team_id="team-1",
            ),
        )
        client = MagicMock(spec=AnkorBackendClient)
        client.find_athlete = AsyncMock(return_value=expected)
        tool = FindAthleteTool(client)
        tool_input = AthleteLookupRequest(org_id="org-1", query="Jane Doe")

        result = await tool.run(tool_input)

        client.find_athlete.assert_awaited_once_with(tool_input)
        assert result == expected

    asyncio.run(run_test())


def test_list_evaluation_templates_tool_calls_backend_client() -> None:
    async def run_test() -> None:
        expected = EvaluationTemplateListResponse(
            count=1,
            templates=[
                EvaluationTemplateSummary(
                    template_id="template-1",
                    name="Game Readiness",
                    description="Pregame readiness template",
                    is_active=True,
                )
            ],
        )
        client = MagicMock(spec=AnkorBackendClient)
        client.list_evaluation_templates = AsyncMock(return_value=expected)
        tool = ListEvaluationTemplatesTool(client)
        tool_input = ListEvaluationTemplatesInput(org_id="org-1", team_id="team-1")

        result = await tool.run(tool_input)

        client.list_evaluation_templates.assert_awaited_once_with(
            org_id="org-1",
            team_id="team-1",
        )
        assert result == expected

    asyncio.run(run_test())


def test_create_evaluation_draft_tool_calls_backend_client() -> None:
    async def run_test() -> None:
        expected = EvaluationDraftResponse(
            status=ResolutionStatus.PENDING_CONFIRMATION,
            draft=EvaluationDraft(
                org_id="org-1",
                coach_id="coach-1",
                team_id="team-1",
                athlete_id="athlete-1",
                scorecard_template_id="template-1",
                items=[{"skill_id": "skill-1", "rating": 4}],
            ),
            confirmation_prompt="Confirm this draft evaluation?",
        )
        client = MagicMock(spec=AnkorBackendClient)
        client.create_evaluation_draft = AsyncMock(return_value=expected)
        tool = CreateEvaluationDraftTool(client)
        tool_input = EvaluationDraftRequest(
            org_id="org-1",
            coach_id="coach-1",
            team_id="team-1",
            athlete_id="athlete-1",
            scorecard_template_id="template-1",
            items=[{"skill_id": "skill-1", "rating": 4}],
        )

        result = await tool.run(tool_input)

        client.create_evaluation_draft.assert_awaited_once_with(tool_input)
        assert result == expected

    asyncio.run(run_test())


def test_finalize_evaluation_tool_calls_backend_client() -> None:
    async def run_test() -> None:
        expected = FinalizeEvaluationResponse(
            evaluation_id="evaluation-1",
            status="submitted",
            message="Evaluation finalized",
        )
        client = MagicMock(spec=AnkorBackendClient)
        client.finalize_evaluation = AsyncMock(return_value=expected)
        tool = FinalizeEvaluationTool(client)
        tool_input = FinalizeEvaluationInput(evaluation_id="evaluation-1")

        result = await tool.run(tool_input)

        client.finalize_evaluation.assert_awaited_once_with(
            evaluation_id="evaluation-1"
        )
        assert result == expected

    asyncio.run(run_test())


def test_tool_registry_exposes_all_tools() -> None:
    client = MagicMock(spec=AnkorBackendClient)

    registry = create_tool_registry(client)
    tool_map = get_tool_map(client)

    assert [tool.name for tool in registry.all()] == [
        "find_athlete",
        "list_evaluation_templates",
        "create_evaluation_draft",
        "finalize_evaluation",
    ]
    assert set(tool_map) == {
        "find_athlete",
        "list_evaluation_templates",
        "create_evaluation_draft",
        "finalize_evaluation",
    }
