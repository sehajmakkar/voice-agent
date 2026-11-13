# Decisions

Every lasting technical decision: tech stack, architecture, interfaces, metrics, thresholds.

**Status:** `Proposed` (waiting for Sehaj) · `Accepted` · `Superseded by D-xxx` · `Rejected`
**Rule:** never rewrite an accepted decision. Add a new entry that supersedes it.

> **2026-11-07:** Sehaj asked Claude to finalise the tech stack. D-003 to D-012 were decided on that
> basis and are marked Accepted. Any of them can still be challenged with a superseding entry.

### Template

```
## D-000: Title
- **Date:** YYYY-MM-DD · **Status:** Proposed · **Phase / task:** plan x.y
- **Context:** what forced the decision
- **Options:** A, B, C, each with its main pro/con
- **Decision:** what we chose
- **Trade-offs:** what we gave up
- **Revisit if:** the signal that would make us change it
- **Links:** C-xxx, L-xxx
```

---

## D-001: Cascaded pipeline (STT → LLM → TTS), not speech-to-speech
- **Date:** 2026-11-06 · **Status:** Accepted (it's the premise of the project) · **Phase:** all
- **Context:** realtime speech-to-speech models give low latency and natural prosody, but they're one model end to end.
- **Options:**
  - **Speech-to-speech:** lowest latency and natural prosody. But you can't swap STT per language, there are few strong Indic code-switching options, it's hard to inspect, and tool-call grounding is harder to control.
  - **Cascaded pipeline:** each stage can be swapped, traced and evaluated on its own, and routing per language becomes possible. But latency adds up across stages.
- **Decision:** cascaded pipeline. Swar's whole value (per-language routing, per-stage tracing, failover) only exists when the stages are separate.
- **Trade-offs:** higher latency floor, and prosody can be lost between stages. Latency engineering (Phases 2, 6) has to make up for that.
- **Revisit if:** a speech-to-speech model handles Indian code-switching on 8 kHz audio well. Even then, keep it as one more routable "provider".
- **Links:** L-002

## D-002: Python + asyncio
- **Date:** 2026-11-06 · **Status:** Accepted · **Phase:** 0
- **Context:** we need a language for a realtime, I/O-heavy pipeline with many concurrent streams.
- **Options:** Python (both leading voice frameworks and most provider SDKs, ML tooling for LID/turn models) · Node/TS (strong WebSocket ergonomics, weaker ML) · Go (great concurrency, thin voice/ML ecosystem).
- **Decision:** Python 3.12 with asyncio.
- **Trade-offs:** GIL and per-process CPU limits. CPU-heavy work (resampling, local models) must stay off the event loop, and scaling means multiple worker processes (Phase 10).
- **Revisit if:** event-loop lag dominates latency under load in Phase 10.
- **Links:** L-004

## D-003: Seven headline metrics, always baseline vs Swar
- **Date:** 2026-11-06, finalised 2026-11-07 · **Status:** Accepted · **Phase / task:** plan 0.1
- **Context:** the original README had three eval sections with conflicting targets (C-001), about 30 metrics in total.
- **Options:** the full catalogue (thorough, impossible to present) · the 8-metric version · a short list.
- **Decision:** 7 headline metrics in the README and the `make eval` report: response time (P50 < 800 ms / P95 < 1.2 s), switch cost (< 50 ms, 0 words lost), transcription accuracy (WER/CER vs the best single provider), failover (< 300 ms recovery, < 1% dead-air turns), turn-taking (< 5% bad cut-offs), task success (> 90%), cost per minute. Each one answers one claim the README makes.
- **Supporting metrics** (internal, in Grafana and plan tasks, not headline claims): language-ID accuracy and latency, flip-flop rate, wrong-script rate, per-stage time to first byte, tool-call latency.
- **Trade-offs:** 800 ms P50 is less aggressive than 600 ms, but it's honest for a cascaded pipeline. Tighten it once the baseline is known.
- **Revisit if:** the Phase 2 baseline is already well under 800 ms.
- **Links:** C-001

## D-004: Voice framework: Pipecat (over LiveKit Agents)
- **Date:** 2026-11-07 · **Status:** Accepted · **Phase / task:** plan 0.6
- **Context:** we need transport, VAD and a pipeline without building them ourselves, while still being able to insert custom stages (router, replay buffer, turn controller) between audio input and STT.
- **Options:**
  - **Pipecat:** the pipeline is a chain of frame processors, so a custom processor drops in anywhere. It's transport-agnostic (WebRTC, WebSocket telephony serializers), has many STT/TTS integrations including Indian providers, ships Silero VAD and Smart Turn, and has OpenTelemetry tracing.
  - **LiveKit Agents:** excellent WebRTC infrastructure and SIP, its own turn-detector model, built-in fallback adapters. The agent-session abstraction is higher-level, so inserting a custom routing stage in front of STT is less direct, and it's tied to running a LiveKit server.
- **Decision:** Pipecat.
- **Trade-offs:** a weaker signal to LiveKit, and Pipecat's own WebRTC/SIP story is lighter. Mitigated by D-005: the core doesn't depend on Pipecat, so it could be connected to LiveKit later.
- **Revisit if:** inserting the router turns out to fight Pipecat's frame model in Phase 3.
- **Links:** C-005, L-009

## D-005: A framework-independent core, with our own STT/TTS adapters
- **Date:** 2026-11-07 · **Status:** Accepted · **Phase / task:** plan 3.1
- **Context:** Pipecat's built-in STT/TTS services each open and own their provider connection. Warm connection pools, replaying buffered audio into a different provider, and speculative dual-streaming all need control *across* providers, which a single service can't give.
- **Options:** use Pipecat's built-in services and switch between them · write our own adapters in a plain-Python core (`swar.core`) and expose them to Pipecat through one custom `SwarSTT` / `SwarTTS` processor.
- **Decision:** our own adapters and router in `swar.core` (pure asyncio, no Pipecat imports). Pipecat glue lives in `swar.pipeline`. **Phase 1's baseline uses Pipecat's built-in services**, which also makes it a fair "off-the-shelf" baseline.
- **Trade-offs:** more code to write and maintain per provider (raw WebSocket protocols). That's also the main learning value, and it makes the core reusable with LiveKit.
- **Links:** C-008, L-007

## D-006: Measure before optimising (phase order)
- **Date:** 2026-11-06 · **Status:** Accepted · **Phase:** plan structure
- **Decision:** tracing (Phase 2) and the benchmark (Phase 4) come before the router (5) and switching (6). Naive switching (5.3) is measured before optimised switching (6) so the headline result is a real before/after. The eval harness (7) comes before turn-taking (8).
- **Trade-offs:** the "cool" work starts later. In exchange, every claim has a baseline.

## D-007: Transport and telephony: SmallWebRTC for development, Twilio for phone calls
- **Date:** 2026-11-07 · **Status:** Superseded by D-013 · **Phase:** 1, 10
- **Options:** Daily (hosted WebRTC, needs an account) · LiveKit server · Pipecat SmallWebRTC (peer-to-peer, local) · for phone calls: Twilio, Exotel, Plivo.
- **Decision:** SmallWebRTC for browser calls during development. **Twilio** Media Streams for the first phone number (fast self-serve setup). **Exotel** for an Indian number only if its business KYC is possible for an individual.
- **Trade-offs:** a Twilio non-Indian number means international calling for Indian testers. Peer-to-peer WebRTC isn't how production scales, but production-scale WebRTC isn't what this project is about.
- **Links:** C-010, L-010

## D-008: Providers: STT, TTS, LLM
- **Date:** 2026-11-07 · **Status:** Accepted · **Phase:** 0.3, 3
- **STT:** **Sarvam** (Indian-language specialist) and **Deepgram** (fast, global, multilingual). Routing needs at least two meaningfully different providers, and these are the two ends. **Smallest** or **Gnani** are added only if self-serve API access works out (checked in 0.3).
- **TTS:** **Sarvam Bulbul** (natural Indian voices) and **Cartesia** (very low latency). Two providers make TTS failover possible.
- **LLM:** **Gemini Flash-tier** primary (fast first token, low cost, good Hinglish) and **OpenAI mini-tier** as fallback. Exact model IDs are pinned in config, and the choice is confirmed by measured time-to-first-token in Phase 2.
- **Trade-offs:** more providers means more adapters and more benchmark cost (C-006). Two per stage is the minimum for routing and failover to mean anything.
- **Revisit if:** the Phase 4 benchmark shows a third provider clearly winning one language mix.

## D-009: Observability: OpenTelemetry + Jaeger + Grafana, no custom dashboard
- **Date:** 2026-11-07 · **Status:** Accepted · **Phase:** 2
- **Context:** the original plan had a Next.js dashboard.
- **Options:** a custom Next.js dashboard (looks good, weeks of frontend work) · Jaeger for traces + Grafana on Postgres for metrics (standard, a few hours) · a hosted service (Honeycomb, Langfuse).
- **Decision:** OpenTelemetry spans → Jaeger (per-turn waterfall) and turn metrics in Postgres → Grafana (P50/P95 by provider and language mix). The demo report comes from `make eval` (markdown + matplotlib charts).
- **Trade-offs:** a less custom-looking UI. The target companies care about the measurements, not a bespoke dashboard, and the saved time goes into the core work.
- **Revisit if:** the demo video needs a custom live view (Phase 11). If so, build only that one view.

## D-010: Storage and server: Postgres + Redis, FastAPI
- **Date:** 2026-11-07 · **Status:** Accepted · **Phase:** 2, 9, 10
- **Decision:** **Postgres** for calls, turns, stage timings, bookings and benchmark results (SQLAlchemy 2.0 async + Alembic migrations). **Redis** only from Phase 10, for live call state shared across workers; before that, in-process state is enough. **FastAPI** for WebRTC signalling and a small API (telephony webhooks join in Phase 12).
- **Trade-offs:** delaying Redis keeps early phases simple. The cost is a refactor of where call state lives in Phase 10, a known and contained change.

## D-011: VAD and turn detection: start with Silero + Smart Turn
- **Date:** 2026-11-07 · **Status:** Accepted · **Phase:** 1, 8
- **Decision:** Silero VAD from day one. In Phase 8, evaluate Pipecat's open-source Smart Turn model on Hinglish pauses *before* building anything custom. The Swar-specific work is the Hinglish tuning and the backchannel classifier.
- **Revisit if:** Smart Turn performs badly on Hinglish (then: fine-tune it, or combine it with transcript rules).

## D-012: Tooling and deployment
- **Date:** 2026-11-07 · **Status:** Accepted · **Phase:** 0.2, 10
- **Tooling:** uv (environments + lockfile), ruff (lint + format), pytest + pytest-asyncio, pre-commit, GitHub Actions.
- **Deployment:** Docker Compose on **one VM in an India region**. No Kubernetes.
- **Why an India region:** the callers, Sarvam and the Indian telephony providers are all in India. Network round trips count against the latency budget (C-009).
- **Trade-offs:** one VM caps concurrency, but Phase 10 measures exactly that cap, and the result is useful on its own.

## D-013: Browser-only demo; phone numbers later (supersedes D-007)
- **Date:** 2026-11-10 · **Status:** Accepted (Sehaj's call) · **Phase:** 1, 10, 11, 12
- **Context:** Sehaj decided the whole demo runs in the browser, with an Indian phone number added after the demo.
- **Decision:** SmallWebRTC browser calls for everything up to and including the v2 demo, also when it's hosted publicly (Phase 10). Phone numbers (an Indian number via Exotel or Twilio India) move to Phase 12. The benchmark still tests **8 kHz phone-quality audio** alongside browser audio.
- **Why:** removes KYC paperwork and telephony costs from the critical path. Anyone can try the demo with a link instead of a number. The time goes into the core work (routing, switching, evals).
- **Trade-offs:**
  - Weaker signal to Exotel and Callab (and partly Retell) until Phase 12.
  - Browser audio (16–48 kHz Opus) is much cleaner than phone audio, so the live demo is the *easy* case. The 8 kHz benchmark keeps the hard case measured and honest.
  - A public peer-to-peer WebRTC demo needs HTTPS and a TURN server (C-011).
- **Revisit if:** a target company asks specifically for a phone demo. Then pull Phase 12 earlier; nothing in the core blocks it.
- **Links:** C-010, C-011, L-010

## D-014: Project setup details: settings, hooks, enforced architecture rules
- **Date:** 2026-11-10 · **Status:** Proposed · **Phase / task:** plan 0.2
- **Settings:** `pydantic-settings` reads `.env` into one typed `Settings` object. Keys are `SecretStr`, so they never show up in logs or reprs. Every key is optional at import time, and `require()` gives a clear error at the point of use. Alternative: plain `os.environ` + `python-dotenv` (no types, secrets easy to leak in logs).
- **Pre-commit:** ruff runs as a *local* hook through `uv run`, so the hook and CI use exactly the ruff version in `uv.lock` (no second version pinned in the hook config). Plus `detect-private-key` and `check-added-large-files` (500 KB), which stop API keys and audio recordings getting committed.
- **Architecture rules as tests:** "`swar.core` never imports Pipecat" (D-005) is checked by an AST-based test in `tests/test_architecture.py`, not by convention. Alternative: per-directory ruff banned-import config (works, but harder to read and extend).
- **Layout:** compose file lives in `infra/` (run via `make up`), not the repo root, to keep the root uncluttered.
- **Trade-offs:** small. Make is one more tool, but it gives short, memorable commands that are the same locally and in CI.

## D-015: LLM without OpenAI: Gemini primary, Sarvam LLM fallback (supersedes the LLM part of D-008)
- **Date:** 2026-11-10 · **Status:** Dropping OpenAI is **Accepted** (Sehaj has no key). The fallback choice is **Proposed** · **Phase:** 2.6, 5.6
- **Context:** D-008 planned OpenAI as the LLM fallback. There's no OpenAI key, and a fallback is still needed for LLM failover (5.6).
- **Options:**
  - **A second Gemini model** (e.g. a Flash-Lite model): no new account, but it's the same provider, so it doesn't survive a Google-side outage or a slow API.
  - **Sarvam's LLM (`sarvam-105b`):** a genuinely different provider, strong on Indian languages, and the Sarvam key already exists. It needs Sarvam credits (C-012), and its time to first token is unknown.
  - **A new account elsewhere** (e.g. Groq, Anthropic): more setup and billing.
- **Decision (proposed):** Gemini Flash primary, Sarvam LLM fallback. A Gemini Flash-Lite model is the stop-gap fallback until Sarvam has credits. LLM failover isn't needed before Phase 5, so nothing is blocked.
- **Also:** pin exact model IDs in config (e.g. `gemini-3.8-flash`), never aliases like `gemini-flash-latest`. An alias can silently point to a new model and change the frozen baseline. `sarvam-m` being deprecated (C-012) shows that model IDs disappear.
- **Revisit if:** Sarvam's time to first token in 2.6 is too slow for a fallback.

## D-016: First STT streaming shape: events, a shared base class, keys passed in
- **Date:** 2026-11-10 · **Status:** Proposed (first version; formalised in plan 3.1) · **Phase / task:** plan 0.5
- **Event model:** every provider emits `STTEvent(kind, received_at, text, language, endpoint, provider_latency_s)` with `kind` ∈ `partial | final | speech_start | speech_end`. Providers that don't support a kind simply never emit it (Sarvam: no `partial`).
- **Shared base class** (`StreamingSTT`): owns the WebSocket loop (a background sender task + receive loop + clean cancellation in `finally`). Each provider only supplies URL, headers, audio encoding, finish message and a **pure `parse()` function**. Alternative: each provider writes its own loop (more duplication; cancellation bugs get copied).
- **Keys are constructor arguments**; `swar.core` never reads settings or `.env` itself. The caller (script, pipeline) decides where keys come from, which keeps core testable and reusable.
- **Defaults:** Deepgram `nova-3` with `language=multi`, endpointing 300 ms. Sarvam `saaras:v3`, `mode=codemix`, `hi-IN`. Both are starting points to compare in Phase 4.
- **Fixtures:** raw provider messages are recorded with `--save-raw` and replayed in tests (principle 8).
- **Open for 3.1:** a `supports_partials` capability flag (C-014); reconnect/keepalive for warm connections (6.3).

## D-017: Pipecat 1.x, Python capped below 3.14, loose dependency floors
- **Date:** 2026-11-10 · **Status:** Proposed · **Phase / task:** plan 0.6
- **Pipecat version:** 1.15.0 (the 1.x API). Most tutorials and blog posts online show the older 0.0.x API, so we follow the **installed source**, not memory or old examples (C-017).
- **Python:** `requires-python = ">=3.12,<3.14"`. Pipecat can't be resolved for 3.14 yet, and an open-ended range makes uv try to solve for every future Python version. D-002 already targets 3.12.
- **Dependency floors:** `uv add` writes the *newest* version as the minimum (e.g. `soxr>=1.1.0`), which blocked Pipecat (it needs soxr 1.0). Our own direct dependencies now have deliberately loose floors (`numpy>=1.26`, `soxr>=0.5`, `websockets>=13`). The exact versions are still pinned by `uv.lock`, so builds stay reproducible.
- **Runner:** for now, bots run under Pipecat's development runner (`pipecat.runner.run.main`, which serves the prebuilt browser client). Our own FastAPI `server.py` (D-010) replaces it once we need our own endpoints.
- **Revisit if:** Pipecat 2.x lands, or the runner gets in the way of custom endpoints.
