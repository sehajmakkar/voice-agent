import time

import numpy as np

from swar.core.audio.pacing import PacedAudio

RATE = 16_000


async def collect(paced: PacedAudio) -> list[bytes]:
    return [frame async for frame in paced]


async def test_frames_are_20ms_and_last_frame_is_padded() -> None:
    pcm = np.ones(RATE // 10 + 7, dtype=np.int16)  # 100 ms + 7 samples
    frames = await collect(PacedAudio(pcm, RATE, speed=0))
    assert len(frames) == 6  # 5 full frames + 1 padded
    assert {len(f) for f in frames} == {640}


async def test_tail_silence_is_appended_after_speech() -> None:
    pcm = np.ones(RATE // 10, dtype=np.int16)
    paced = PacedAudio(pcm, RATE, tail_silence_s=0.06, speed=0)
    frames = await collect(paced)
    assert len(frames) == 5 + 3
    assert all(f == bytes(640) for f in frames[5:])
    assert paced.speech_end_at is not None


async def test_real_time_pacing_does_not_drift() -> None:
    """1 s of audio at 10x speed should take ~0.1 s, without accumulated sleep error on top."""
    pcm = np.zeros(RATE, dtype=np.int16)
    start = time.monotonic()
    frames = await collect(PacedAudio(pcm, RATE, speed=10))
    elapsed = time.monotonic() - start
    assert len(frames) == 50
    # The last frame is due at 49 * 20 ms / 10 = 98 ms
    assert 0.09 <= elapsed < 0.15
