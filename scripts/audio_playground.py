"""Audio playground (plan 0.4): hear what phone audio does to your voice.

    uv run python scripts/audio_playground.py --record 5      # speak for 5 seconds
    uv run python scripts/audio_playground.py --input my.wav  # or use an existing 16-bit WAV
    add --play to hear each version one after another

Writes four versions to out/playground/ so you can compare them by ear:
    1_original_16k.wav         what the mic heard, 16 kHz
    2_downsampled_8k.wav       phone sample rate: everything above 4 kHz is gone
    3_phone_8k_mulaw.wav       8 kHz + mu-law compression: what a phone line actually carries
    4_phone_back_to_16k.wav    upsampled again: the lost detail does not come back
"""

import argparse
from pathlib import Path

import numpy as np

from swar.core.audio.pcm import (
    MULAW_WIDTH,
    PCM16_WIDTH,
    frame_bytes,
    mulaw_decode,
    mulaw_encode,
    read_wav,
    resample,
    write_wav,
)

OUT = Path("out/playground")
RATE = 16_000


def record(seconds: float) -> np.ndarray:
    import sounddevice as sd  # dev-only dependency

    print(f"Recording {seconds:g} s at {RATE} Hz... speak now (try some Hinglish).")
    pcm = sd.rec(int(seconds * RATE), samplerate=RATE, channels=1, dtype="int16")
    sd.wait()
    return pcm[:, 0]


def play(pcm: np.ndarray, rate: int, label: str) -> None:
    import sounddevice as sd

    print(f"  playing: {label}")
    sd.play(pcm, rate)
    sd.wait()


def band_energy_share(pcm: np.ndarray, rate: int, low_hz: float, high_hz: float) -> float:
    """Share of the signal's energy between low_hz and high_hz."""
    spectrum = np.abs(np.fft.rfft(pcm.astype(np.float64))) ** 2
    freqs = np.fft.rfftfreq(len(pcm), 1 / rate)
    total = spectrum.sum()
    return float(spectrum[(freqs >= low_hz) & (freqs < high_hz)].sum() / total) if total else 0.0


def snr_db(reference: np.ndarray, degraded: np.ndarray) -> float:
    ref = reference.astype(np.float64)
    noise = degraded.astype(np.float64) - ref
    return float(10 * np.log10(np.mean(ref**2) / max(np.mean(noise**2), 1e-12)))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--record", type=float, metavar="SECONDS", help="record from the microphone"
    )
    source.add_argument("--input", type=Path, help="use an existing 16-bit WAV file")
    parser.add_argument("--play", action="store_true", help="play every version after writing it")
    args = parser.parse_args()

    if args.record:
        original, rate = record(args.record), RATE
    else:
        original, rate = read_wav(args.input)
        original = resample(original, rate, RATE)
        print(f"Loaded {args.input} ({rate} Hz), resampled to {RATE} Hz")
        rate = RATE

    seconds = len(original) / rate
    print("\n== What you recorded")
    print(f"  sample rate {rate} Hz · mono · 16-bit · {seconds:.2f} s · {len(original):,} samples")
    print(f"  one 20 ms frame = {rate // 50} samples = {frame_bytes(rate)} bytes")
    print(f"  {seconds / 0.02:.0f} frames of 20 ms in this clip")
    print(f"  peak level {np.abs(original).max() / 32768:.0%} of full scale")

    # The phone path: 16 kHz -> 8 kHz -> mu-law (8 bits) -> decode
    down_8k = resample(original, RATE, 8_000)
    codes = mulaw_encode(down_8k)
    phone_8k = mulaw_decode(codes)
    back_16k = resample(phone_8k, 8_000, RATE)

    print("\n== What a phone line does to it")
    lost = band_energy_share(original, rate, 4_000, 8_000)
    print(f"  energy above 4 kHz (removed by 8 kHz sampling): {lost:.1%}")
    print("    small as a share of energy, but it's where 's', 'f', 'sh' and 'th' live")
    print(f"  mu-law round trip SNR: {snr_db(down_8k, phone_8k):.1f} dB (higher = cleaner)")
    pcm_kbps = RATE * PCM16_WIDTH * 8 / 1000
    phone_kbps = 8_000 * MULAW_WIDTH * 8 / 1000
    print(f"  bandwidth: 16 kHz PCM {pcm_kbps:.0f} kbps -> 8 kHz mu-law {phone_kbps:.0f} kbps")
    print(f"  20 ms phone frame = {frame_bytes(8_000, sample_width=MULAW_WIDTH)} bytes")

    versions = [
        ("1_original_16k.wav", original, RATE),
        ("2_downsampled_8k.wav", down_8k, 8_000),
        ("3_phone_8k_mulaw.wav", phone_8k, 8_000),
        ("4_phone_back_to_16k.wav", back_16k, RATE),
    ]
    print(f"\n== Wrote {OUT}/")
    for name, pcm, r in versions:
        write_wav(OUT / name, pcm, r)
        print(f"  {name}")
        if args.play:
            play(pcm, r, name)


if __name__ == "__main__":
    main()
