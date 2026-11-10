"""Raw streaming STT (plan 0.5): stream a WAV in 20 ms frames at real-time pace.

    uv run python scripts/stream_stt.py --input out/clips/hinglish_booking_16k.wav
    uv run python scripts/stream_stt.py --input my.wav --providers deepgram --deepgram-language hi
    add --save-raw out/raw to record every raw provider message (for test fixtures)

Both providers run concurrently on the same audio. Timeline columns:
    +t      seconds since the script started streaming (one clock for every provider)
    audio   how much audio that provider had been sent at that moment
"""

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from swar.config import get_settings
from swar.core.audio.pacing import PacedAudio
from swar.core.audio.pcm import read_wav, resample
from swar.core.providers.stt.base import StreamingSTT, STTEvent
from swar.core.providers.stt.deepgram import DeepgramSTT
from swar.core.providers.stt.sarvam import SarvamSTT

RATE = 16_000
COLORS = {"deepgram": "\033[36m", "sarvam": "\033[35m"}
RESET, DIM = "\033[0m", "\033[2m"
T0 = time.monotonic()  # shared timeline origin, reset just before streaming starts


@dataclass
class Run:
    provider: StreamingSTT
    audio: PacedAudio
    events: list[STTEvent] = field(default_factory=list)
    error: str | None = None
    called_at: float = 0.0  # when we asked to connect


def show(run: Run, event: STTEvent) -> None:
    t = event.received_at - T0
    start = run.audio.started_at or event.received_at
    sent = min(event.received_at - start, run.audio.duration_s)
    color = COLORS.get(run.provider.name, "")
    label = event.kind + (" ⏎" if event.endpoint else "")
    text = f'"{event.text}"' if event.text else ""
    extra = f"  {DIM}[{event.language}]{RESET}" if event.language else ""
    name = f"{color}{run.provider.name:<9}{RESET}"
    print(f"{name} +{t:5.2f}s  audio {sent:4.2f}s  {label:<14} {text}{extra}")


async def run_one(run: Run) -> None:
    run.called_at = time.monotonic()
    try:
        async for event in run.provider.stream(run.audio):
            run.events.append(event)
            show(run, event)
    except Exception as exc:  # report and keep the other provider running
        run.error = f"{type(exc).__name__}: {exc}"
        print(f"{run.provider.name}: ERROR {run.error}")


def summarise(run: Run) -> None:
    name, a = run.provider.name, run.audio
    print(f"\n── {name}")
    if run.error:
        print(f"  failed: {run.error}")
        return
    start = a.started_at or 0.0
    if a.started_at:
        connect_ms = (a.started_at - run.called_at) * 1000
        print(f"  connect (handshake): {connect_ms:.0f} ms   ← what warm connections remove")
    partials = [e for e in run.events if e.kind == "partial"]
    finals = [e for e in run.events if e.kind == "final"]
    if partials:
        first = partials[0]
        print(f"  first partial:      {first.received_at - start:.2f}s after first audio")
        print(f"    first text: {first.text!r} [{first.language}]  ({len(partials)} partials)")
    else:
        print("  first partial:      none (this provider only sends finished segments)")
    if finals and a.speech_end_at:
        last = finals[-1].received_at - a.speech_end_at
        print(f"  speech end → final: {last * 1000:+.0f} ms   ← the STT part of turn latency")
        reported = [e.provider_latency_s for e in finals if e.provider_latency_s is not None]
        if reported:
            print(f"  provider-reported processing: {', '.join(f'{r:.2f}s' for r in reported)}")
    print(f"  final transcript:   {' '.join(e.text for e in finals) or '(none)'}")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--input", type=Path, required=True, help="16-bit WAV file")
    parser.add_argument("--providers", default="deepgram,sarvam")
    parser.add_argument(
        "--deepgram-language", default="multi", help="multi (code-switching), hi, en-IN, ..."
    )
    parser.add_argument(
        "--sarvam-language", default="hi-IN", help="hi-IN, ta-IN, bn-IN, unknown, ..."
    )
    parser.add_argument(
        "--sarvam-mode", default="codemix", help="codemix, transcribe, translit, ..."
    )
    parser.add_argument(
        "--tail-silence", type=float, default=1.5, help="seconds of silence after the clip"
    )
    parser.add_argument(
        "--save-raw", type=Path, help="directory to write raw provider messages (JSONL)"
    )
    args = parser.parse_args()

    pcm, rate = read_wav(args.input)
    pcm = resample(pcm, rate, RATE)
    settings = get_settings()

    def recorder(name: str):
        if not args.save_raw:
            return None
        args.save_raw.mkdir(parents=True, exist_ok=True)
        path = args.save_raw / f"{name}_{int(time.time())}.jsonl"

        def write(message: dict) -> None:
            with path.open("a") as f:
                f.write(json.dumps(message, ensure_ascii=False) + "\n")

        return write

    providers: list[StreamingSTT] = []
    for name in args.providers.split(","):
        if name == "deepgram":
            providers.append(
                DeepgramSTT(
                    settings.require("deepgram_api_key"),
                    language=args.deepgram_language,
                    on_raw=recorder(name),
                )
            )
        elif name == "sarvam":
            providers.append(
                SarvamSTT(
                    settings.require("sarvam_api_key"),
                    language=args.sarvam_language,
                    mode=args.sarvam_mode,
                    on_raw=recorder(name),
                )
            )
        else:
            parser.error(f"unknown provider {name!r}")

    runs = [Run(p, PacedAudio(pcm, RATE, tail_silence_s=args.tail_silence)) for p in providers]
    global T0
    T0 = time.monotonic()
    print(
        f"Streaming {args.input} ({len(pcm) / RATE:.2f}s + {args.tail_silence}s silence) "
        f"in 20 ms frames at real-time pace\n"
    )
    await asyncio.gather(*(run_one(r) for r in runs))
    for r in runs:
        summarise(r)


if __name__ == "__main__":
    asyncio.run(main())
