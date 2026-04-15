"""Minimal Bedrock voice client abstractions for Nova Sonic sessions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from inspect import isawaitable
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.voice.events import AudioInputChunkEvent


class BedrockSessionConfig(BaseModel):
    """Configuration needed to open a Nova Sonic voice session."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_id: str = Field(min_length=1)
    model_id: str = Field(default="amazon.nova-sonic-v1:0", min_length=1)
    locale: str = Field(default="en-US", min_length=2)
    voice_id: str | None = None


class BedrockBidirectionalStream(Protocol):
    """Bidirectional provider stream contract used by the Sonic session."""

    async def send_audio_event(self, event: AudioInputChunkEvent) -> None:
        """Send one audio chunk into the provider stream."""

    def __aiter__(self) -> AsyncIterator[Mapping[str, Any]]:
        """Iterate provider events emitted by the underlying stream."""

    async def aclose(self) -> None:
        """Close the underlying provider stream."""


class StubBedrockBidirectionalStream:
    """In-memory provider stream used for tests and local development."""

    def __init__(self) -> None:
        self.sent_audio_events: list[AudioInputChunkEvent] = []
        self.is_closed = False
        self._provider_events: asyncio.Queue[Mapping[str, Any] | None] = (
            asyncio.Queue()
        )

    async def send_audio_event(self, event: AudioInputChunkEvent) -> None:
        """Record a caller audio chunk instead of sending it to AWS."""
        if self.is_closed:
            raise RuntimeError("Provider stream is closed.")
        self.sent_audio_events.append(event)

    async def push_provider_event(self, event: Mapping[str, Any]) -> None:
        """Inject a provider event for tests or local development."""
        if self.is_closed:
            raise RuntimeError("Provider stream is closed.")
        await self._provider_events.put(dict(event))

    async def finish(self) -> None:
        """Mark the outgoing provider event stream as complete."""
        await self._provider_events.put(None)

    async def aclose(self) -> None:
        """Close the stub stream."""
        if self.is_closed:
            return
        self.is_closed = True
        await self.finish()

    def __aiter__(self) -> "StubBedrockBidirectionalStream":
        return self

    async def __anext__(self) -> Mapping[str, Any]:
        event = await self._provider_events.get()
        if event is None:
            raise StopAsyncIteration
        return event


type StreamFactory = Callable[
    [BedrockSessionConfig],
    BedrockBidirectionalStream | Awaitable[BedrockBidirectionalStream],
]


class BedrockClient:
    """Small adapter that hides Bedrock streaming implementation details."""

    def __init__(self, *, stream_factory: StreamFactory | None = None) -> None:
        self._stream_factory = stream_factory or _default_stream_factory

    async def open_voice_stream(
        self,
        config: BedrockSessionConfig,
    ) -> BedrockBidirectionalStream:
        """Open a bidirectional voice stream for the given session config."""
        stream = self._stream_factory(config)
        if isawaitable(stream):
            stream = await stream
        return stream


def _default_stream_factory(_: BedrockSessionConfig) -> StubBedrockBidirectionalStream:
    return StubBedrockBidirectionalStream()
