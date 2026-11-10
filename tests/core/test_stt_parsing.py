"""Replay real recorded provider messages (plan 0.5) through the parsers. No network."""

import json
from pathlib import Path

import pytest

from swar.core.providers.stt.deepgram import DeepgramSTT
from swar.core.providers.stt.sarvam import SarvamSTT

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "stt"


def replay(parser, name: str):
    lines = (FIXTURES / name).read_text().splitlines()
    return [e for i, line in enumerate(lines) for e in parser(json.loads(line), float(i))]


def test_deepgram_recorded_stream() -> None:
    events = replay(DeepgramSTT.parse, "deepgram_hinglish_booking.jsonl")
    kinds = [e.kind for e in events]
    assert kinds[0] == "speech_start"
    assert kinds[-1] == "speech_end"  # UtteranceEnd
    assert "partial" in kinds
    finals = [e for e in events if e.kind == "final"]
    assert len(finals) == 3
    text = " ".join(e.text for e in finals)
    assert "appointment" in text and "Thursday" in text
    assert finals[-1].endpoint  # speech_final on the last segment
    assert all(e.text for e in events if e.kind in ("partial", "final"))  # empty results dropped


def test_sarvam_recorded_stream() -> None:
    events = replay(SarvamSTT.parse, "sarvam_hinglish_booking.jsonl")
    assert [e.kind for e in events] == [
        "speech_start", "speech_end", "final", "speech_start", "speech_end", "final",
    ]  # fmt: skip
    finals = [e for e in events if e.kind == "final"]
    assert all(e.endpoint and e.language == "hi-IN" for e in finals)
    assert all(e.provider_latency_s is not None for e in finals)
    assert "Thursday" in finals[-1].text


def test_sarvam_error_message_raises() -> None:
    with pytest.raises(RuntimeError, match="Sarvam STT error"):
        SarvamSTT.parse({"type": "error", "data": {"message": "bad audio"}}, 0.0)


def test_deepgram_ignores_metadata_and_empty_results() -> None:
    empty = {"type": "Results", "is_final": True, "channel": {"alternatives": [{"transcript": ""}]}}
    assert DeepgramSTT.parse(empty, 0.0) == []
    assert DeepgramSTT.parse({"type": "Metadata"}, 0.0) == []
