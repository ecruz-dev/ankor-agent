import asyncio
import json

import httpx
import pytest

from app.clients.ankor_backend import (
    AnkorBackendClient,
    AnkorBackendError,
)
from app.schemas.athlete import AthleteLookupRequest
from app.schemas.evaluation import EvaluationDraftRequest
from app.schemas.session import ResolutionStatus


def test_find_athlete_parses_response_and_sends_auth_header() -> None:
    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/api/voice/athletes/find"
            assert request.headers["Accept"] == "application/json"
            assert request.headers["Authorization"] == "Bearer test-token"
            assert json.loads(request.content.decode("utf-8")) == {
                "org_id": "org-1",
                "query": "Jane Doe",
                "max_results": 5,
            }
            return httpx.Response(
                200,
                json={
                    "query": "Jane Doe",
                    "status": "resolved",
                    "selected_athlete": {
                        "athlete_id": "athlete-1",
                        "full_name": "Jane Doe",
                        "team_id": "team-1",
                        "team_name": "Varsity",
                    },
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://backend.test",
            transport=transport,
        ) as http_client:
            client = AnkorBackendClient(
                base_url="https://backend.test",
                api_token="test-token",
                http_client=http_client,
            )
            response = await client.find_athlete(
                AthleteLookupRequest(org_id="org-1", query="Jane Doe")
            )

        assert response.status is ResolutionStatus.RESOLVED
        assert response.selected_athlete is not None
        assert response.selected_athlete.athlete_id == "athlete-1"

    asyncio.run(run_test())


def test_list_evaluation_templates_parses_backend_items_shape() -> None:
    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "GET"
            assert request.url.path == "/api/voice/evaluation-templates"
            assert request.url.params["org_id"] == "org-1"
            return httpx.Response(
                200,
                json={
                    "count": 1,
                    "items": [
                        {
                            "id": "template-1",
                            "name": "Game Readiness",
                            "description": "Pregame readiness template",
                            "is_active": True,
                        }
                    ],
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://backend.test",
            transport=transport,
        ) as http_client:
            client = AnkorBackendClient(
                base_url="https://backend.test",
                http_client=http_client,
            )
            response = await client.list_evaluation_templates(org_id="org-1")

        assert response.count == 1
        assert response.templates[0].template_id == "template-1"
        assert response.templates[0].name == "Game Readiness"

    asyncio.run(run_test())


def test_create_evaluation_draft_parses_response() -> None:
    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/api/voice/evaluations/drafts"
            assert json.loads(request.content.decode("utf-8")) == {
                "org_id": "org-1",
                "coach_id": "coach-1",
                "team_id": "team-1",
                "athlete_id": "athlete-1",
                "scorecard_template_id": "template-1",
                "items": [
                    {
                        "skill_id": "skill-1",
                        "rating": 4,
                    }
                ],
            }
            return httpx.Response(
                201,
                json={
                    "status": "pending_confirmation",
                    "draft": {
                        "org_id": "org-1",
                        "coach_id": "coach-1",
                        "team_id": "team-1",
                        "athlete_id": "athlete-1",
                        "scorecard_template_id": "template-1",
                        "items": [
                            {
                                "skill_id": "skill-1",
                                "rating": 4,
                            }
                        ],
                    },
                    "confirmation_prompt": "Confirm this draft evaluation?",
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://backend.test",
            transport=transport,
        ) as http_client:
            client = AnkorBackendClient(
                base_url="https://backend.test",
                http_client=http_client,
            )
            response = await client.create_evaluation_draft(
                EvaluationDraftRequest(
                    org_id="org-1",
                    coach_id="coach-1",
                    team_id="team-1",
                    athlete_id="athlete-1",
                    scorecard_template_id="template-1",
                    items=[{"skill_id": "skill-1", "rating": 4}],
                )
            )

        assert response.status is ResolutionStatus.PENDING_CONFIRMATION
        assert response.draft is not None
        assert response.draft.athlete_id == "athlete-1"

    asyncio.run(run_test())


def test_finalize_evaluation_raises_backend_error_for_non_2xx() -> None:
    async def run_test() -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            assert request.url.path == "/api/voice/evaluations/evaluation-1/finalize"
            return httpx.Response(
                500,
                json={"message": "database unavailable"},
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            base_url="https://backend.test",
            transport=transport,
        ) as http_client:
            client = AnkorBackendClient(
                base_url="https://backend.test",
                http_client=http_client,
            )
            with pytest.raises(AnkorBackendError) as exc_info:
                await client.finalize_evaluation(evaluation_id="evaluation-1")

        assert exc_info.value.backend_status_code == 500
        assert exc_info.value.error_code == "ankor_backend_response_error"
        assert exc_info.value.status_code == 502

    asyncio.run(run_test())
