"""Async helpers for audio flowing into a bidirectional voice session."""

from __future__ import annotations

import asyncio
from typing import Self

from app.utils.errors import AppError
from app.voice.events import AudioInputChunkEvent


class AudioStreamClosedError(AppError):
    """Raised when audio is written after the input stream has been closed."""


class AudioInputStream:
    """Queue-backed async iterator used to forward caller audio into a session."""

    def __init__(self, *, max_queue_size: int = 0) -> None:
        self._queue: asyncio.Queue[AudioInputChunkEvent | None] = asyncio.Queue(
            maxsize=max_queue_size
        )
        self._closed = False

    @property
    def is_closed(self) -> bool:
        """Return whether the input stream has been closed."""
        return self._closed

    async def write(self, event: AudioInputChunkEvent) -> None:
        """Queue an audio chunk for forwarding to the provider stream."""
        if self._closed:
            raise AudioStreamClosedError(
                "Audio input stream is closed.",
                error_code="audio_stream_closed",
            )
        await self._queue.put(event)

    async def close(self) -> None:
        """Stop the stream and terminate any active async iteration."""
        if self._closed:
            return
        self._closed = True
        await self._queue.put(None)

    def __aiter__(self) -> Self:
        return self

    async def __anext__(self) -> AudioInputChunkEvent:
        item = await self._queue.get()
        if item is None:
            raise StopAsyncIteration
        return item
