"""A pass-through processor that shows what flows through one point of a Pipecat pipeline.

Put it between any two processors to see the frames there. Audio frames arrive ~50 times a second,
so they're counted and summarised; every other frame is logged as it passes. See L-009.
"""

import time
from collections import Counter

from loguru import logger
from pipecat.frames.frames import (
    BotSpeakingFrame,
    Frame,
    InputAudioRawFrame,
    OutputAudioRawFrame,
    UserSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

#: high-frequency frames: counted, not logged one by one
NOISY = (InputAudioRawFrame, OutputAudioRawFrame, UserSpeakingFrame, BotSpeakingFrame)


def describe(frame: Frame) -> str:
    if isinstance(frame, VADUserStartedSpeakingFrame):
        return f"(VAD needed {frame.start_secs:.2f}s of speech to decide)"
    if isinstance(frame, VADUserStoppedSpeakingFrame):
        return f"(VAD waited {frame.stop_secs:.2f}s of silence to decide)"
    return ""


class FrameLogger(FrameProcessor):
    def __init__(self, label: str, summary_every_s: float = 5.0, **kwargs) -> None:
        super().__init__(**kwargs)
        self.label = label
        self.summary_every_s = summary_every_s
        self.counts: Counter[tuple[str, str]] = Counter()
        self._last_summary = time.monotonic()

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        # Always call the parent first: it handles Start/Cancel/Interruption bookkeeping.
        await super().process_frame(frame, direction)
        arrow = "↓" if direction == FrameDirection.DOWNSTREAM else "↑"
        name = type(frame).__name__
        if isinstance(frame, NOISY):
            self.counts[(name, arrow)] += 1
            self._maybe_summarise()
        else:
            logger.info(f"[{self.label}] {arrow} {name} {describe(frame)}".rstrip())
        await self.push_frame(frame, direction)  # a logger must never swallow frames

    def _maybe_summarise(self) -> None:
        now = time.monotonic()
        if now - self._last_summary < self.summary_every_s:
            return
        seconds = now - self._last_summary
        rates = ", ".join(
            f"{n} {a} {c / seconds:.0f}/s" for (n, a), c in sorted(self.counts.items())
        )
        logger.info(f"[{self.label}] last {seconds:.0f}s: {rates}")
        self.counts.clear()
        self._last_summary = now
