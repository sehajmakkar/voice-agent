"""Parrot (plan 0.6): records what you say and plays it back when you stop. A learning tool.

It exercises the pieces the real agent needs: VAD start/stop frames, swallowing input audio,
and pushing output audio. It also shows a problem the real system has to solve:

VAD only confirms "user started speaking" after `start_secs` of speech (0.2 s by default). Audio
that arrived before that moment would be lost, so the first syllable gets clipped. The fix is a
*pre-roll*: always keep the last ~0.5 s of audio and prepend it when speech is confirmed. That's
the same idea as the audio replay buffer that keeps 0 words lost on a provider switch (plan 6.1).
"""

import time
from collections import deque

from loguru import logger
from pipecat.frames.frames import (
    Frame,
    InputAudioRawFrame,
    SpeechOutputAudioRawFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

FRAME_MS = 20


class Parrot(FrameProcessor):
    def __init__(self, pre_roll_s: float = 0.5, **kwargs) -> None:
        super().__init__(**kwargs)
        self._pre_roll: deque[bytes] = deque(maxlen=round(pre_roll_s * 1000 / FRAME_MS))
        self._utterance = bytearray()
        self._listening = False
        self._sample_rate = 16_000
        self.replays: list[float] = []  # seconds replayed per utterance (for tests and logs)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, InputAudioRawFrame):
            self._sample_rate = frame.sample_rate
            if self._listening:
                self._utterance.extend(frame.audio)
            else:
                self._pre_roll.append(frame.audio)
            return  # swallow mic audio: otherwise it would be played straight back out

        if isinstance(frame, VADUserStartedSpeakingFrame):
            self._listening = True
            self._utterance = bytearray(b"".join(self._pre_roll))  # the clipped first syllable
            self._pre_roll.clear()
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            self._listening = False
            # True end of speech is frame.timestamp - frame.stop_secs (C-016): VAD only
            # confirms the stop after that much silence.
            confirmed_after_ms = (time.time() - (frame.timestamp - frame.stop_secs)) * 1000
            logger.info(
                f"[parrot] utterance {self._seconds(self._utterance):.2f}s; stop confirmed "
                f"{confirmed_after_ms:.0f} ms after you stopped (stop_secs={frame.stop_secs})"
            )
            # Order matters: downstream must see "user stopped" before the bot's reply audio.
            await self.push_frame(frame, direction)
            await self._replay()
            return

        await self.push_frame(frame, direction)

    def _seconds(self, pcm: bytes | bytearray) -> float:
        return len(pcm) / (2 * self._sample_rate)

    async def _replay(self) -> None:
        audio, self._utterance = bytes(self._utterance), bytearray()
        self.replays.append(self._seconds(audio))
        chunk = self._sample_rate * FRAME_MS // 1000 * 2
        for i in range(0, len(audio), chunk):
            # The output transport queues these and plays them at real-time pace.
            # SpeechOutputAudioRawFrame (not plain OutputAudioRawFrame) tells the transport this
            # is the bot *speaking*, so it emits BotStarted/StoppedSpeakingFrame. Without those,
            # nothing downstream knows the bot is mid-sentence, and barge-in can't work (C-018).
            frame = SpeechOutputAudioRawFrame(
                audio[i : i + chunk], self._sample_rate, num_channels=1
            )
            await self.push_frame(frame)
