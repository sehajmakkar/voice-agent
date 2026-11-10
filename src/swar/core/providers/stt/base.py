"""Shared streaming-STT plumbing (first version, from plan 0.5; formalised in plan 3.1).

Every provider here works the same way:
  1. open a WebSocket,
  2. a background task sends audio frames while the main loop reads transcript messages,
  3. when the audio ends, send the provider's "finish" message and drain what's left.

Subclasses only say how to build the URL and headers, encode audio, and parse messages.
Parsing is a pure function of (message, receive time) so it can be tested without a network.
"""

import asyncio
import contextlib
import json
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterable, AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Literal

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosedOK

EventKind = Literal["partial", "final", "speech_start", "speech_end"]


@dataclass(frozen=True)
class STTEvent:
    kind: EventKind
    received_at: float  # time.monotonic() when the message arrived
    text: str = ""
    language: str | None = None
    endpoint: bool = False  # provider thinks the speaker finished this utterance
    provider_latency_s: float | None = None  # processing time the provider reports, if any


class StreamingSTT(ABC):
    name: str
    #: after the finish message, stop if nothing arrives for this long
    drain_timeout_s: float = 3.0

    def __init__(self, on_raw: Callable[[dict[str, Any]], None] | None = None) -> None:
        self._on_raw = on_raw  # hook for recording raw messages as test fixtures

    @abstractmethod
    def url(self) -> str: ...

    @abstractmethod
    def headers(self) -> dict[str, str]: ...

    @abstractmethod
    def encode_audio(self, frame: bytes) -> str | bytes: ...

    @abstractmethod
    def finish_message(self) -> str: ...

    @staticmethod
    @abstractmethod
    def parse(message: dict[str, Any], received_at: float) -> list[STTEvent]: ...

    async def stream(self, audio: AsyncIterable[bytes]) -> AsyncIterator[STTEvent]:
        async with connect(self.url(), additional_headers=self.headers(), open_timeout=10) as ws:
            finished_sending: float | None = None

            async def send_audio() -> None:
                nonlocal finished_sending
                async for frame in audio:
                    await ws.send(self.encode_audio(frame))
                await ws.send(self.finish_message())
                finished_sending = time.monotonic()

            sender = asyncio.create_task(send_audio(), name=f"{self.name}-sender")
            last_message_at = time.monotonic()
            try:
                while True:
                    if sender.done() and sender.exception():
                        raise sender.exception()  # type: ignore[misc]
                    if (
                        finished_sending is not None
                        and time.monotonic() - max(finished_sending, last_message_at)
                        > self.drain_timeout_s
                    ):
                        break  # provider went quiet after we finished: nothing more is coming
                    try:
                        # Short timeout so the checks above run regularly.
                        # Cancelling recv() is safe in websockets' asyncio client: no data is lost.
                        raw = await asyncio.wait_for(ws.recv(), timeout=0.2)
                    except TimeoutError:
                        continue
                    except ConnectionClosedOK:
                        break  # provider closed cleanly after flushing its last results
                    last_message_at = time.monotonic()
                    message = json.loads(raw)
                    if self._on_raw:
                        self._on_raw(message)
                    for event in self.parse(message, last_message_at):
                        yield event
            finally:
                # Runs on normal exit, errors, and when the caller stops early (e.g. barge-in).
                sender.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await sender
