"""HTTP client for calling the ANKOR backend."""

from __future__ import annotations

import json
from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, Self, TypeVar, cast

import httpx
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

from app.config.settings import Settings, get_settings
from app.schemas.athlete import AthleteLookupRequest, AthleteLookupResponse
from app.schemas.evaluation import EvaluationDraftRequest, EvaluationDraftResponse
from app.utils.errors import AppError

ResponseModelT = TypeVar("ResponseModelT", bound=BaseModel)


class EvaluationTemplateSummary(BaseModel):
    """Minimal evaluation template data returned by the ANKOR backend."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    template_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("template_id", "id"),
    )
    name: str = Field(min_length=1)
    description: str | None = None
    is_active: bool = True


class EvaluationTemplateListResponse(BaseModel):
    """Typed response for evaluation template listing."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    count: int = Field(default=0, ge=0)
    templates: list[EvaluationTemplateSummary] = Field(
        default_factory=list,
        validation_alias=AliasChoices("templates", "items"),
    )


class FinalizeEvaluationResponse(BaseModel):
    """Result of finalizing an evaluation draft."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    evaluation_id: str = Field(
        min_length=1,
        validation_alias=AliasChoices("evaluation_id", "id"),
    )
    status: str = Field(min_length=1)
    message: str | None = None


class AnkorBackendError(AppError):
    """Raised when the ANKOR backend request fails or returns invalid data."""

    def __init__(
        self,
        message: str,
        *,
        backend_status_code: int | None = None,
        error_code: str = "ankor_backend_error",
        response_body: str | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            status_code=HTTPStatus.BAD_GATEWAY,
        )
        self.backend_status_code = backend_status_code
        self.response_body = response_body


class AnkorBackendClient:
    """Typed async client for the ANKOR backend HTTP API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_token: str | None = None,
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )
        self._client.headers.update(self._default_headers(api_token))

    @classmethod
    def from_settings(
        cls,
        settings: Settings | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> "AnkorBackendClient":
        """Build a client from application settings."""
        resolved_settings = settings or get_settings()
        return cls(
            base_url=str(resolved_settings.ankor_backend_base_url),
            api_token=resolved_settings.ankor_backend_api_token,
            timeout_seconds=resolved_settings.ankor_backend_timeout_seconds,
            http_client=http_client,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the owned HTTP client."""
        if self._owns_client:
            await self._client.aclose()

    async def find_athlete(
        self,
        request: AthleteLookupRequest,
    ) -> AthleteLookupResponse:
        """Find an athlete through the ANKOR backend."""
        payload = await self._request(
            "POST",
            "/api/voice/athletes/find",
            json_body=request.model_dump(mode="json", exclude_none=True),
        )
        return self._validate_response(
            AthleteLookupResponse,
            payload,
            operation="find_athlete",
        )

    async def list_evaluation_templates(
        self,
        *,
        org_id: str,
        team_id: str | None = None,
    ) -> EvaluationTemplateListResponse:
        """List active evaluation templates."""
        payload = await self._request(
            "GET",
            "/api/voice/evaluation-templates",
            params={"org_id": org_id, "team_id": team_id},
        )
        return self._validate_response(
            EvaluationTemplateListResponse,
            payload,
            operation="list_evaluation_templates",
        )

    async def create_evaluation_draft(
        self,
        request: EvaluationDraftRequest,
    ) -> EvaluationDraftResponse:
        """Create a draft evaluation through the ANKOR backend."""
        payload = await self._request(
            "POST",
            "/api/voice/evaluations/drafts",
            json_body=request.model_dump(mode="json", exclude_none=True),
        )
        return self._validate_response(
            EvaluationDraftResponse,
            payload,
            operation="create_evaluation_draft",
        )

    async def finalize_evaluation(
        self,
        *,
        evaluation_id: str,
    ) -> FinalizeEvaluationResponse:
        """Finalize an existing evaluation draft."""
        payload = await self._request(
            "POST",
            f"/api/voice/evaluations/{evaluation_id}/finalize",
        )
        return self._validate_response(
            FinalizeEvaluationResponse,
            payload,
            operation="finalize_evaluation",
        )

    @staticmethod
    def _default_headers(api_token: str | None) -> dict[str, str]:
        """Build placeholder authentication and content negotiation headers."""
        headers = {"Accept": "application/json"}
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        request_kwargs: dict[str, Any] = {}
        if json_body is not None:
            request_kwargs["json"] = json_body
        if params is not None:
            request_kwargs["params"] = {
                key: value for key, value in params.items() if value is not None
            }

        try:
            response = await self._client.request(method, path, **request_kwargs)
        except httpx.TimeoutException as exc:
            raise AnkorBackendError(
                "ANKOR backend request timed out",
                error_code="ankor_backend_timeout",
            ) from exc
        except httpx.RequestError as exc:
            raise AnkorBackendError(
                "ANKOR backend request failed",
                error_code="ankor_backend_request_failed",
            ) from exc

        if response.is_error:
            raise AnkorBackendError(
                (
                    f"ANKOR backend returned {response.status_code}: "
                    f"{self._extract_error_message(response)}"
                ),
                backend_status_code=response.status_code,
                error_code="ankor_backend_response_error",
                response_body=response.text,
            )

        if response.status_code == HTTPStatus.NO_CONTENT:
            return {}

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise AnkorBackendError(
                "ANKOR backend returned invalid JSON",
                backend_status_code=response.status_code,
                error_code="ankor_backend_invalid_json",
                response_body=response.text,
            ) from exc

        if not isinstance(payload, dict):
            raise AnkorBackendError(
                "ANKOR backend returned an unexpected payload shape",
                backend_status_code=response.status_code,
                error_code="ankor_backend_invalid_payload",
                response_body=response.text,
            )

        return cast(dict[str, Any], payload)

    @staticmethod
    def _extract_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return response.text or "request failed"

        if isinstance(payload, dict):
            for key in ("message", "detail", "error"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value

        return response.text or "request failed"

    @staticmethod
    def _validate_response(
        model_type: type[ResponseModelT],
        payload: Mapping[str, Any],
        *,
        operation: str,
    ) -> ResponseModelT:
        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            raise AnkorBackendError(
                f"ANKOR backend returned invalid data for {operation}",
                error_code="ankor_backend_invalid_response",
                response_body=json.dumps(payload, default=str),
            ) from exc
