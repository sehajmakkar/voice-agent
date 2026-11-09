"""PCM audio basics: frame sizes, resampling, G.711 mu-law, and WAV I/O.

All audio inside Swar is mono 16-bit signed PCM (`np.int16`) unless a function says otherwise.
See learnings.md L-001.
"""

import wave
from pathlib import Path

import numpy as np
import soxr

PCM16_WIDTH = 2  # bytes per 16-bit sample
MULAW_WIDTH = 1  # bytes per mu-law sample

# G.711 mu-law constants (ITU-T G.711, same algorithm as the classic Sun g711.c).
# The encoder works on 14-bit samples; the decoder returns 16-bit samples.
_MULAW_BIAS = 0x84  # 132 in 16-bit terms (33 in 14-bit terms)
_MULAW_CLIP_14 = 8159  # largest 14-bit magnitude before the bias is added
_MULAW_SEGMENT_ENDS = np.array([0x3F, 0x7F, 0xFF, 0x1FF, 0x3FF, 0x7FF, 0xFFF, 0x1FFF])


def frame_bytes(sample_rate: int, frame_ms: int = 20, sample_width: int = PCM16_WIDTH) -> int:
    """Bytes in one mono frame. 20 ms at 16 kHz PCM16 = 320 samples = 640 bytes."""
    samples = sample_rate * frame_ms // 1000
    return samples * sample_width


def resample(pcm: np.ndarray, from_rate: int, to_rate: int) -> np.ndarray:
    """High-quality resampling. Downsampling low-pass filters first, so nothing aliases."""
    if from_rate == to_rate:
        return pcm
    return soxr.resample(pcm, from_rate, to_rate).astype(np.int16)


def mulaw_encode(pcm: np.ndarray) -> np.ndarray:
    """int16 PCM -> uint8 mu-law codes.

    Mu-law spends its 8 bits logarithmically: small amplitudes get fine steps and loud ones
    coarse steps, which matches how hearing works. Each code is
    [sign:1][exponent (segment):3][mantissa (step within segment):4], with all bits inverted.
    """
    # 16-bit -> 14-bit. `>>` on a negative number rounds towards -infinity (-5 >> 2 == -2),
    # so negative samples end up with a slightly larger magnitude. That asymmetry is part of
    # the standard; skipping it makes ~0.6% of negative samples land one step off.
    x14 = pcm.astype(np.int32) >> 2
    negative = x14 < 0
    magnitude = np.minimum(np.where(negative, -x14, x14), _MULAW_CLIP_14) + (_MULAW_BIAS >> 2)
    # Segment (exponent) = first segment whose upper end is >= the magnitude -> 0..7 (8 = clip)
    segment = np.searchsorted(_MULAW_SEGMENT_ENDS, magnitude, side="left")
    in_range = segment < 8
    mantissa = (magnitude >> (np.minimum(segment, 7) + 1)) & 0x0F
    code = np.where(in_range, (segment << 4) | mantissa, 0x7F)
    # Sign and inversion in one step: positive codes are XORed with 0xFF, negative with 0x7F
    return (code ^ np.where(negative, 0x7F, 0xFF)).astype(np.uint8)


def mulaw_decode(codes: np.ndarray) -> np.ndarray:
    """uint8 mu-law codes -> int16 PCM."""
    c = ~codes.astype(np.int32) & 0xFF
    sign = c & 0x80
    exponent = (c >> 4) & 0x07
    mantissa = c & 0x0F
    magnitude = (((mantissa << 3) + _MULAW_BIAS) << exponent) - _MULAW_BIAS
    return np.where(sign != 0, -magnitude, magnitude).astype(np.int16)


def read_wav(path: str | Path) -> tuple[np.ndarray, int]:
    """Read a 16-bit WAV. Stereo is mixed down to mono. Returns (samples, sample_rate)."""
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != PCM16_WIDTH:
            raise ValueError(f"{path}: expected 16-bit PCM, got {8 * wav.getsampwidth()}-bit")
        rate, channels = wav.getframerate(), wav.getnchannels()
        pcm = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
    if channels > 1:
        pcm = pcm.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return pcm.copy(), rate


def write_wav(path: str | Path, pcm: np.ndarray, sample_rate: int) -> None:
    """Write mono 16-bit PCM to a WAV file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(PCM16_WIDTH)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm.astype("<i2").tobytes())
