"""Send audio at real-time pace, like a live microphone would."""

import asyncio
import time
from collections.abc import AsyncIterator

import numpy as np

from swar.core.audio.pcm import PCM16_WIDTH


class PacedAudio:
    """Yields 16-bit PCM frames on a real-time schedule.

    Each frame is scheduled at `start + i * frame_duration` (an absolute deadline) instead of
    `sleep(frame_duration)` after each send. Relative sleeps drift: every send and wake-up adds a
    little delay, and over a long call the stream falls behind real time.

    After the clip, `tail_silence_s` of zeros is sent, the way a real caller goes quiet after
    speaking. That's what lets a provider's own end-of-speech detection fire.
    """

    def __init__(
        self,
        pcm: np.ndarray,
        sample_rate: int,
        frame_ms: int = 20,
        tail_silence_s: float = 0.0,
        speed: float = 1.0,
    ) -> None:
        samples_per_frame = sample_rate * frame_ms // 1000
        self.frame_bytes = samples_per_frame * PCM16_WIDTH
        self.frame_s = frame_ms / 1000
        self.speed = speed  # 0 = as fast as possible (tests); 1 = real time
        self._speech = pcm.astype("<i2").tobytes()
        self._silence_frames = round(tail_silence_s / self.frame_s)
        self.duration_s = len(pcm) / sample_rate
        self.started_at: float | None = None  # monotonic time of the first frame
        self.speech_end_at: float | None = None  # monotonic time the last speech frame was sent

    async def _wait_for_slot(self, index: int) -> None:
        if self.speed <= 0 or self.started_at is None:
            return
        deadline = self.started_at + index * self.frame_s / self.speed
        delay = deadline - time.monotonic()
        if delay > 0:
            await asyncio.sleep(delay)

    async def __aiter__(self) -> AsyncIterator[bytes]:
        index = 0
        for offset in range(0, len(self._speech), self.frame_bytes):
            frame = self._speech[offset : offset + self.frame_bytes]
            frame = frame.ljust(self.frame_bytes, b"\x00")  # pad the last partial frame
            await self._wait_for_slot(index)
            if self.started_at is None:
                self.started_at = time.monotonic()
            yield frame
            index += 1
        self.speech_end_at = time.monotonic()
        silence = bytes(self.frame_bytes)
        for _ in range(self._silence_frames):
            await self._wait_for_slot(index)
            yield silence
            index += 1
