import warnings

import numpy as np
import pytest

from swar.core.audio.pcm import (
    MULAW_WIDTH,
    frame_bytes,
    mulaw_decode,
    mulaw_encode,
    read_wav,
    resample,
    write_wav,
)


def _sine(freq: float, rate: int, seconds: float = 1.0, amplitude: int = 10_000) -> np.ndarray:
    t = np.arange(int(rate * seconds)) / rate
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.int16)


def test_frame_sizes() -> None:
    assert frame_bytes(16_000) == 640  # 320 samples x 2 bytes
    assert frame_bytes(8_000) == 320
    # 8 kHz mu-law: what a phone line carries per 20 ms
    assert frame_bytes(8_000, sample_width=MULAW_WIDTH) == 160
    assert frame_bytes(48_000, frame_ms=10) == 960


def test_mulaw_matches_reference_for_every_int16_value() -> None:
    """Bit-exact against CPython's audioop (G.711) for all 65,536 inputs and all 256 codes."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        audioop = pytest.importorskip("audioop")  # removed in Python 3.13

    every_sample = np.arange(-32768, 32768, dtype=np.int16)
    expected = np.frombuffer(audioop.lin2ulaw(every_sample.tobytes(), 2), dtype=np.uint8)
    np.testing.assert_array_equal(mulaw_encode(every_sample), expected)

    every_code = np.arange(256, dtype=np.uint8)
    expected_pcm = np.frombuffer(audioop.ulaw2lin(every_code.tobytes(), 2), dtype=np.int16)
    np.testing.assert_array_equal(mulaw_decode(every_code), expected_pcm)


def test_mulaw_round_trip_keeps_speech_quality() -> None:
    signal = _sine(440, 8_000)
    decoded = mulaw_decode(mulaw_encode(signal)).astype(np.float64)
    noise = decoded - signal
    snr_db = 10 * np.log10(np.mean(signal.astype(np.float64) ** 2) / np.mean(noise**2))
    assert snr_db > 30  # G.711 gives roughly 35-38 dB on speech-level signals


def test_downsampling_to_8k_removes_everything_above_4k() -> None:
    """Nyquist: an 8 kHz signal can only carry frequencies below 4 kHz."""
    low, high = _sine(1_000, 16_000), _sine(6_000, 16_000)
    assert len(resample(low, 16_000, 8_000)) == 8_000

    def energy(x: np.ndarray) -> float:
        return float(np.mean(x.astype(np.float64) ** 2))

    assert energy(resample(low, 16_000, 8_000)) > 0.9 * energy(low)  # 1 kHz survives
    assert energy(resample(high, 16_000, 8_000)) < 0.01 * energy(high)  # 6 kHz is gone


def test_wav_round_trip(tmp_path) -> None:
    pcm = _sine(300, 16_000, seconds=0.5)
    write_wav(tmp_path / "a.wav", pcm, 16_000)
    loaded, rate = read_wav(tmp_path / "a.wav")
    assert rate == 16_000
    np.testing.assert_array_equal(loaded, pcm)
