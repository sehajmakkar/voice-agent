"""Sarvam streaming STT over a raw WebSocket.

Protocol (read from Sarvam's SDK source, sarvamai 0.1.45):
  URL      wss://api.sarvam.ai/speech-to-text/ws?language-code=..&model=..&mode=..
  header   Api-Subscription-Key
  send     {"audio": {"data": <base64 audio>, "sample_rate": 16000, "encoding": "audio/wav"}}
           {"type": "flush"} forces any buffered audio to be transcribed
  receive  {"type": "data",   "data": {"transcript", "language_code", "metrics": {...}}}
           {"type": "events", "data": {"signal_type": "START_SPEECH" | "END_SPEECH"}}
           {"type": "error",  "data": {...}}
Unlike Deepgram there are no partial transcripts: each "data" message is a finished segment,
sent after Sarvam's own VAD decides the speaker paused. The socket stays open after a flush.
"""

import base64
import json
from typing import Any
from urllib.parse import urlencode

from swar.core.providers.stt.base import StreamingSTT, STTEvent


class SarvamSTT(StreamingSTT):
    name = "sarvam"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "saaras:v3",
        language: str = "hi-IN",  # "unknown" asks Sarvam to detect it
        mode: str = "codemix",  # transcribe | translate | verbatim | translit | codemix
        sample_rate: int = 16_000,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key
        self.sample_rate = sample_rate
        self.params = {
            "language-code": language,
            "model": model,
            "mode": mode,
            "sample_rate": sample_rate,
            "input_audio_codec": "pcm_s16le",
            "vad_signals": "true",
            "flush_signal": "true",
        }

    def url(self) -> str:
        return "wss://api.sarvam.ai/speech-to-text/ws?" + urlencode(self.params)

    def headers(self) -> dict[str, str]:
        return {"Api-Subscription-Key": self._api_key}

    def encode_audio(self, frame: bytes) -> str:
        data = base64.b64encode(frame).decode("ascii")
        return json.dumps(
            {"audio": {"data": data, "sample_rate": self.sample_rate, "encoding": "audio/wav"}}
        )

    def finish_message(self) -> str:
        return json.dumps({"type": "flush"})

    @staticmethod
    def parse(message: dict[str, Any], received_at: float) -> list[STTEvent]:
        kind, data = message.get("type"), message.get("data") or {}
        if kind == "error":
            raise RuntimeError(f"Sarvam STT error: {data}")
        if kind == "events":
            signal = data.get("signal_type")
            if signal == "START_SPEECH":
                return [STTEvent("speech_start", received_at)]
            if signal == "END_SPEECH":
                return [STTEvent("speech_end", received_at)]
            return []
        if kind != "data":
            return []
        text = (data.get("transcript") or "").strip()
        if not text:
            return []
        metrics = data.get("metrics") or {}
        return [
            STTEvent(
                "final",
                received_at,
                text=text,
                language=data.get("language_code"),
                endpoint=True,
                provider_latency_s=metrics.get("processing_latency"),
            )
        ]
