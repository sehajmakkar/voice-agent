"""Deepgram streaming STT over a raw WebSocket.

Protocol: binary 16-bit PCM frames in; JSON messages out:
  Results        transcript; is_final=False is a partial that may still change,
                 is_final=True locks that segment, speech_final=True means Deepgram's
                 endpointing thinks the utterance ended
  SpeechStarted  VAD heard speech (needs vad_events=true)
  UtteranceEnd   a gap after the last word (needs utterance_end_ms)
  Metadata       sent once at the end
Finish by sending {"type": "CloseStream"}; Deepgram flushes and closes the socket.
"""

import json
from typing import Any
from urllib.parse import urlencode

from swar.core.providers.stt.base import StreamingSTT, STTEvent


class DeepgramSTT(StreamingSTT):
    name = "deepgram"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "nova-3",
        language: str = "multi",  # multilingual code-switching mode
        sample_rate: int = 16_000,
        endpointing_ms: int = 300,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key
        self.params = {
            "model": model,
            "language": language,
            "encoding": "linear16",
            "sample_rate": sample_rate,
            "channels": 1,
            "interim_results": "true",
            "punctuate": "true",
            "smart_format": "true",
            "endpointing": endpointing_ms,
            "vad_events": "true",
            "utterance_end_ms": 1000,
        }

    def url(self) -> str:
        return "wss://api.deepgram.com/v1/listen?" + urlencode(self.params)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self._api_key}"}

    def encode_audio(self, frame: bytes) -> bytes:
        return frame

    def finish_message(self) -> str:
        return json.dumps({"type": "CloseStream"})

    @staticmethod
    def parse(message: dict[str, Any], received_at: float) -> list[STTEvent]:
        kind = message.get("type")
        if kind == "SpeechStarted":
            return [STTEvent("speech_start", received_at)]
        if kind == "UtteranceEnd":
            return [STTEvent("speech_end", received_at)]
        if kind != "Results":
            return []
        alternative = (message.get("channel", {}).get("alternatives") or [{}])[0]
        text = alternative.get("transcript", "").strip()
        if not text:
            return []  # Deepgram sends empty results during silence
        languages = alternative.get("languages") or []
        return [
            STTEvent(
                "final" if message.get("is_final") else "partial",
                received_at,
                text=text,
                language=languages[0] if languages else None,
                endpoint=bool(message.get("speech_final")),
            )
        ]
