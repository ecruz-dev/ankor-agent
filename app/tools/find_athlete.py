"""Tool for resolving an athlete before evaluation work."""

from __future__ import annotations

from app.clients.ankor_backend import AnkorBackendClient
from app.schemas.athlete import AthleteLookupRequest, AthleteLookupResponse


class FindAthleteTool:
    """Use when the assistant needs to resolve an athlete from a spoken name."""

    name = "find_athlete"
    description = (
        "Find the most likely athlete match before creating or reviewing "
        "an evaluation."
    )
    input_model = AthleteLookupRequest
    output_model = AthleteLookupResponse

    def __init__(self, client: AnkorBackendClient) -> None:
        self._client = client

    async def run(self, tool_input: AthleteLookupRequest) -> AthleteLookupResponse:
        """Resolve an athlete using the ANKOR backend client."""
        return await self._client.find_athlete(tool_input)
