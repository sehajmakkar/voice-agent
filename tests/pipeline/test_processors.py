"""Pipecat processors tested with Pipecat's own run_test harness: no browser, no network."""

from pipecat.frames.frames import (
    InputAudioRawFrame,
    OutputAudioRawFrame,
    SpeechOutputAudioRawFrame,
    TextFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.tests.utils import run_test

from swar.pipeline.frame_logger import FrameLogger
from swar.pipeline.parrot import Parrot

RATE = 16_000
FRAME = bytes(RATE * 20 // 1000 * 2)  # one 20 ms frame of silence


def mic(n: int) -> list[InputAudioRawFrame]:
    return [InputAudioRawFrame(FRAME, RATE, 1) for _ in range(n)]


async def test_frame_logger_passes_every_frame_through_unchanged() -> None:
    logger = FrameLogger("t")
    down, _ = await run_test(
        logger,
        frames_to_send=[*mic(3), TextFrame("hi")],
        expected_down_frames=[InputAudioRawFrame] * 3 + [TextFrame],
    )
    assert down[-1].text == "hi"
    assert sum(logger.counts.values()) == 3  # audio counted, not logged individually


async def test_parrot_replays_utterance_including_pre_roll() -> None:
    parrot = Parrot(pre_roll_s=0.1)  # keeps the last 5 frames before VAD confirms speech
    frames = [
        *mic(10),  # before VAD fires: only the last 5 are kept as pre-roll
        VADUserStartedSpeakingFrame(start_secs=0.2),
        *mic(20),  # the utterance
        VADUserStoppedSpeakingFrame(stop_secs=0.6),
    ]
    down, _ = await run_test(parrot, frames_to_send=frames)

    # Mic audio is swallowed; only VAD frames and replayed audio come out
    assert not any(isinstance(f, InputAudioRawFrame) for f in down)
    replayed = [f for f in down if isinstance(f, OutputAudioRawFrame)]
    assert len(replayed) == 25  # 5 pre-roll + 20 utterance frames
    # Must be marked as speech, or the transport never emits BotStartedSpeakingFrame (C-018)
    assert all(isinstance(f, SpeechOutputAudioRawFrame) for f in replayed)
    assert parrot.replays == [0.5]
    assert isinstance(down[-1], OutputAudioRawFrame)  # stop frame first, then the replay


async def test_parrot_without_pre_roll_would_clip_the_start() -> None:
    parrot = Parrot(pre_roll_s=0.0)
    frames = [
        *mic(10),
        VADUserStartedSpeakingFrame(),
        *mic(20),
        VADUserStoppedSpeakingFrame(),
    ]
    await run_test(parrot, frames_to_send=frames)
    assert parrot.replays == [0.4]  # the 0.2 s before VAD confirmed speech is gone
