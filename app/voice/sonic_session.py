"""Bidirectional Nova Sonic session abstraction."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, Self

from app.clients.bedrock_client import (
    BedrockBidirectionalStream,
    BedrockClient,
    BedrockSessionConfig,
)
from app.utils.errors import AppError
from app.voice.audio_stream import AudioInputStream
from app.voice.events import (
    AssistantAudioReplyEvent,
    AssistantTextReplyEvent,
    AudioEncoding,
    AudioInputChunkEvent,
    ToolRequestTriggerEvent,
    VoiceSessionEvent,
)
from app.voice.transcript_parser import TranscriptParser


class SonicSessionError(AppError):
    """Raised when the Sonic session cannot continue safely."""


class SonicSession:
    """Manage a minimal bidirectional Nova Sonic session lifecycle."""

    _ASSISTANT_TEXT_TYPES = frozenset(
        {
            "assistant_text",
            "assistant_text_reply",
        }
    )
    _ASSISTANT_AUDIO_TYPES = frozenset(
        {
            "assistant_audio",
            "assistant_audio_reply",
        }
    )
    _TOOL_REQUEST_TYPES = frozenset(
        {
            "tool_request",
            "tool_request_trigger",
        }
    )

    def __init__(
        self,
        *,
        config: BedrockSessionConfig,
        bedrock_client: BedrockClient,
        transcript_parser: TranscriptParser | None = None,
        audio_stream: AudioInputStream | None = None,
    ) -> None:
        self._config = config
        self._bedrock_client = bedrock_client
        self._transcript_parser = transcript_parser or TranscriptParser()
        self._audio_stream = audio_stream or AudioInputStream()
        self._provider_stream: BedrockBidirectionalStream | None = None
        self._event_queue: asyncio.Queue[VoiceSessionEvent | None] = asyncio.Queue()
        self._forward_task: asyncio.Task[None] | None = None
        self._consume_task: asyncio.Task[None] | None = None
        self._started = False
        self._closed = False
        self._event_queue_closed = False
        self._task_error: Exception | None = None

    @property
    def session_id(self) -> str:
        """Return the configured session identifier."""
        return self._config.session_id

    @property
    def is_started(self) -> bool:
        """Return whether the provider stream has been opened."""
        return self._started

    @property
    def is_closed(self) -> bool:
        """Return whether the session has been closed."""
        return self._closed

    async def __aenter__(self) -> Self:
        return await self.start()

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> VoiceSessionEvent:
        event = await self.next_event()
        if event is None:
            raise StopAsyncIteration
        return event

    async def start(self) -> Self:
        """Open the provider stream and start the session background tasks."""
        if self._closed:
            raise SonicSessionError(
                "Sonic session is already closed.",
                error_code="sonic_session_closed",
            )
        if self._started:
            return self

        self._provider_stream = await self._bedrock_client.open_voice_stream(
            self._config
        )
        self._forward_task = asyncio.create_task(
            self._forward_audio(),
            name=f"sonic-forward-{self.session_id}",
        )
        self._consume_task = asyncio.create_task(
            self._consume_provider_events(),
            name=f"sonic-consume-{self.session_id}",
        )
        self._started = True
        return self

    async def send_audio_chunk(
        self,
        audio_bytes: bytes,
        *,
        chunk_index: int,
        sample_rate_hz: int = 16000,
        channel_count: int = 1,
        encoding: AudioEncoding = AudioEncoding.PCM_S16LE,
        is_end_of_turn: bool = False,
    ) -> AudioInputChunkEvent:
        """Queue a caller audio chunk for forwarding to the provider stream."""
        if not self._started:
            raise SonicSessionError(
                "Sonic session has not been started.",
                error_code="sonic_session_not_started",
            )
        if self._closed:
            raise SonicSessionError(
                "Sonic session is already closed.",
                error_code="sonic_session_closed",
            )

        event = AudioInputChunkEvent(
            session_id=self.session_id,
            chunk_index=chunk_index,
            audio_bytes=audio_bytes,
            sample_rate_hz=sample_rate_hz,
            channel_count=channel_count,
            encoding=encoding,
            is_end_of_turn=is_end_of_turn,
        )
        await self._audio_stream.write(event)
        return event

    async def next_event(self) -> VoiceSessionEvent | None:
        """Return the next typed provider event, or ``None`` when the stream ends."""
        if not self._started:
            raise SonicSessionError(
                "Sonic session has not been started.",
                error_code="sonic_session_not_started",
            )

        event = await self._event_queue.get()
        if event is None:
            if self._task_error is not None:
                raise SonicSessionError(
                    "Sonic session stream failed.",
                    error_code="sonic_session_stream_failed",
                ) from self._task_error
            return None
        return event

    async def aclose(self) -> None:
        """Close the session and stop its background tasks."""
        if self._closed:
            return
        self._closed = True
        await self._audio_stream.close()
        if self._forward_task is not None:
            await asyncio.gather(self._forward_task, return_exceptions=True)
        if self._provider_stream is not None:
            await self._provider_stream.aclose()
        if self._consume_task is not None:
            await asyncio.gather(self._consume_task, return_exceptions=True)
        if self._forward_task is None and self._consume_task is None:
            await self._close_event_queue()

    async def _forward_audio(self) -> None:
        assert self._provider_stream is not None

        try:
            async for audio_event in self._audio_stream:
                await self._provider_stream.send_audio_event(audio_event)
        except Exception as exc:
            self._task_error = exc
            await self._provider_stream.aclose()

    async def _consume_provider_events(self) -> None:
        assert self._provider_stream is not None

        try:
            async for provider_event in self._provider_stream:
                parsed_event = self._parse_provider_event(provider_event)
                if parsed_event is not None:
                    await self._event_queue.put(parsed_event)
        except Exception as exc:
            self._task_error = exc
        finally:
            await self._close_event_queue()

    async def _close_event_queue(self) -> None:
        if self._event_queue_closed:
            return
        self._event_queue_closed = True
        await self._event_queue.put(None)

    def _parse_provider_event(
        self,
        provider_event: Mapping[str, Any],
    ) -> VoiceSessionEvent | None:
        transcript_event = self._transcript_parser.parse_event(
            provider_event,
            session_id=self.session_id,
        )
        if transcript_event is not None:
            return transcript_event

        root = _unwrap_payload(provider_event)
        event_type = _normalize_event_type(root)

        if event_type in self._ASSISTANT_TEXT_TYPES:
            text = _extract_string(root, "text", "content", "response")
            if text is None:
                return None
            return AssistantTextReplyEvent(session_id=self.session_id, text=text)

        if event_type in self._ASSISTANT_AUDIO_TYPES:
            audio_bytes = _extract_audio_bytes(root)
            if audio_bytes is None:
                return None
            return AssistantAudioReplyEvent(
                session_id=self.session_id,
                audio_bytes=audio_bytes,
                sequence_number=_extract_int(root, "sequence_number", "sequence") or 0,
                mime_type=_extract_string(root, "mime_type", "content_type")
                or "audio/pcm",
                is_final_chunk=_extract_bool(root, "is_final_chunk", "final") or False,
            )

        if event_type in self._TOOL_REQUEST_TYPES:
            tool_name = _extract_string(root, "tool_name", "name")
            if tool_name is None:
                return None
            arguments = root.get("arguments", root.get("input", {}))
            if not isinstance(arguments, Mapping):
                arguments = {}
            return ToolRequestTriggerEvent(
                session_id=self.session_id,
                tool_name=tool_name,
                arguments=dict(arguments),
                request_id=_extract_string(root, "request_id", "id"),
            )

        return None


def _unwrap_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    root = payload
    for key in ("event", "payload"):
        nested = root.get(key)
        if isinstance(nested, Mapping):
            root = nested
    return root


def _normalize_event_type(payload: Mapping[str, Any]) -> str | None:
    raw_type = _extract_string(payload, "type", "event_type", "kind")
    if raw_type is None:
        return None
    return raw_type.lower().replace(".", "_").replace("-", "_")


def _extract_string(payload: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _extract_int(payload: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            continue
        return value
    return None


def _extract_bool(payload: Mapping[str, Any], *keys: str) -> bool | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    return None


def _extract_audio_bytes(payload: Mapping[str, Any]) -> bytes | None:
    for key in ("audio_bytes", "audio", "chunk"):
        value = payload.get(key)
        if isinstance(value, bytes) and value:
            return value
        if isinstance(value, bytearray) and value:
            return bytes(value)
    return None
