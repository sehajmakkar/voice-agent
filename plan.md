# Swar: Build Plan

**Current phase:** Phase 0: Foundations

## How to use this plan

- Work one phase at a time, in order. The order is deliberate: **measure first** (Phases 1–2),
**get data next** (Phases 3–4), and **optimise last** (Phases 5+). See D-006.
- Each task should fit in one sitting (about 1–3 hours). If it doesn't, split it.
- Tick tasks with the commit hash: `- [x] 2.3 ... (a1b2c3d)`.
- Each phase lists **Learn first** (entries in `learnings.md`), an **exit criterion**, and the
**companies it signals to**.
- When a phase ends: record its numbers, then update `decisions.md`, `challenges.md` and
`learnings.md`. A short public post is optional but worth doing.

**Stack (final, see decisions.md):** Python 3.12 · Pipecat · SmallWebRTC (browser; phone numbers later) · FastAPI ·
STT: Sarvam, Deepgram · TTS: Sarvam Bulbul, Cartesia · LLM: Gemini Flash (Sarvam LLM fallback) ·
Silero VAD + Smart Turn · Postgres + Redis · OpenTelemetry + Jaeger + Grafana · Docker Compose · uv / ruff / pytest

## Milestones (cut lines)

| Milestone | Phases | What you can show | Start applying? |
|---|---|---|---|
| **v0: Apply-ready** | 0–4 | Working Hinglish agent, per-turn latency tracing, **public Indic STT benchmark on browser and phone-quality audio** | **Yes, start outreach here** |
| **v1: Core claim** | + 5–6 | Language routing, failover, switch cost: naive vs Swar | Headline result |
| **v2: Complete** | + 7–11 | Eval harness in CI, turn-taking, tools, hosted browser demo anyone can try, load/cost numbers, demo video | Full story |
| **Later** | 12 | Real Indian phone number, outbound calls | After the demo |

Don't wait for v2 to reach out. v0 alone is a credible conversation starter for the India-stack
and eval companies.

---

## Phase 0: Foundations

**Goal:** a working dev environment, and comfort with raw audio and streaming *before* Pipecat hides it.
**Learn first:** L-001 audio basics, L-004 asyncio & cancellation, L-009 Pipecat frames & processors.

- [x] 0.1 Merge the README eval sections into one metric set; simplify the README; finalise the stack (C-001, D-003)
- [x] 0.2 Project setup with uv: `pyproject.toml`, ruff, pytest + pytest-asyncio, pre-commit, `src/swar/` layout, `.env.example`, `infra/docker-compose.yml` (Postgres, Jaeger, Grafana). Fill in Commands in CLAUDE.md (D-012, D-014). _(not committed yet)_
  - [x] 0.2a Start Docker Desktop, run `make up`, and check that Jaeger (:16686) and Grafana (:3000) open and Grafana's Postgres datasource connects
- [~] 0.3 Get API keys: Sarvam, Deepgram, Cartesia, Gemini. Make a table of free credits, rate limits and supported languages (C-006, D-008). ~~OpenAI~~: no key; dropped (D-015)
  - [x] Keys verified (2026-11-10): Deepgram, Cartesia, Gemini work
  - [x] Sarvam credits added; language ID, LLM (`sarvam-105b`), TTS and STT all verified (C-012)
  - [ ] Fill in the free-credit amounts in the table below
  - [ ] Optional: check whether Smallest / Gnani offer self-serve API access

  | Provider | Key | Credits | Hindi | Tamil | Bengali | Notes |
  |---|---|---|---|---|---|---|
  | Deepgram (STT) | ✅ | _?_ | ✅ | ✅ | ✅ | Nova-3 streaming lists hi, ta, bn, en-IN, plus a multilingual variant |
  | Cartesia (TTS) | ✅ | _?_ | 59 voices | 13 voices | 7 voices | API version header `2025-04-16` |
  | Gemini (LLM) | ✅ | _?_ | n/a | n/a | n/a | Many Flash models available; pin an exact ID, never `-latest` (D-015) |
  | Sarvam (STT, TTS, LLM) | ✅ | _?_ | ✅ | ✅ | ✅ | `sarvam-105b` is a reasoning model (C-013). STT writes English words in Devanagari. Test calls used REST; live use needs the streaming endpoints |
- [~] 0.4 Audio playground: record mic → WAV; print sample rate / channels / bit depth; resample 16k → 8k and listen; μ-law encode/decode round trip
  - [x] `swar/core/audio/pcm.py`: frame sizes, resampling (soxr), G.711 μ-law written by hand, WAV I/O; bit-exact against the reference for all 65,536 inputs
  - [x] `scripts/audio_playground.py`, checked on a synthetic clip
  - [ ] **Sehaj:** run `uv run python scripts/audio_playground.py --record 5 --play` with your own Hinglish and listen to the four versions
- [x] 0.5 Raw streaming STT, no framework: stream a WAV to Deepgram **and** Sarvam over WebSocket in 20 ms chunks at real-time pace; print partials vs finals with timestamps. (This is the core of the Phase 3 adapters.) (D-016)
  - Built: `core/audio/pacing.py` (drift-free real-time pacing), `core/providers/stt/{base,deepgram,sarvam}.py`, `scripts/stream_stt.py`; replay tests on recorded messages in `tests/fixtures/stt/`
  - **First numbers** (Cartesia-generated 7.5 s Hinglish clip, from India, 2 runs):

    | | Deepgram (nova-3, multi) | Sarvam (saaras:v3, codemix) |
    |---|---|---|
    | Connect (handshake) | **893–1378 ms** (~300 ms round trip) | **157–163 ms** (~40 ms round trip) |
    | First partial | 1.3 s after first audio, wrongly tagged Persian (`fa`) | none: no partials at all |
    | Speech end → final | 766–854 ms | 682–700 ms (provider-reported processing 0.05–0.16 s) |
    | Script | "doctor" in Latin; "दस" vs "10" varies between runs | "डॉक्टर" in Devanagari, "appointment" in Latin |
- [ ] 0.6 Pipecat basics: run an echo bot over SmallWebRTC; write one custom `FrameProcessor` that logs every frame type passing through it (D-004)
- [ ] 0.7 Read what Pipecat (and LiveKit) already ship for STT/TTS fallback or service switching. Write down how Swar goes beyond it (C-005)

**Exit:** you can explain PCM, frames, sample rates, partial vs final transcripts and Pipecat's frame flow without notes.
**Signals to:** foundation for everyone.

## Phase 1: Baseline voice agent

**Goal:** talk to an agent in the browser in Hinglish, using **Pipecat's built-in services**: one STT, one LLM, one TTS.
**This is the "Baseline"** that every Swar number is compared against.
**Learn first:** L-002 streaming pipeline, L-003 VAD vs turn detection, L-010 WebRTC vs WebSocket.

- [ ] 1.1 Pipeline: SmallWebRTC → Silero VAD → Deepgram or Sarvam STT → Gemini → Cartesia or Sarvam TTS → speaker, served by FastAPI
- [ ] 1.2 Voice system prompt: short replies, no markdown, numbers and dates spoken naturally, reply in the caller's language mix
- [ ] 1.3 Default barge-in: TTS stops when the caller speaks. Write down what goes wrong with "haan", "hmm"
- [ ] 1.4 Clinic-booking conversation with hardcoded slots (no real tools yet)
- [ ] 1.5 **Freeze the baseline:** save the exact providers, models and settings in `configs/baseline.yaml`. Never change it afterwards (add new configs instead)
- [ ] 1.6 Rough latency on 10 turns from logs; write it down
- [ ] 1.7 Record 5 Hinglish conversations: the first clips for the test set

**Exit:** a 2-minute Hinglish booking conversation works end to end; the baseline config is frozen.
**Signals to:** Pipecat/Daily, Vapi, Retell.

## Phase 2: Tracing & baseline numbers

**Goal:** see exactly where the time goes in every turn.
**Learn first:** L-005 percentiles & latency budgets, L-006 OpenTelemetry.

- [ ] 2.1 Define the turn lifecycle events: `speech_end` → `stt_final` → `llm_first_token` → `tts_first_audio` → `audio_out_start`
- [ ] 2.2 Turn on Pipecat's OpenTelemetry tracing; add Swar's own spans and attributes (provider, language mix); export to Jaeger
- [ ] 2.3 Postgres schema + Alembic: calls, turns, stage timings
- [ ] 2.4 Grafana: per-stage latency panels and P50/P95 by provider
- [ ] 2.5 P50 / P95 / P99 over 30+ turns: **the baseline latency number**
- [ ] 2.6 Measure time-to-first-token for 2–3 Gemini Flash models and Sarvam's LLM on the same Hinglish prompts; pin the winner's exact model ID (D-015). Measure time to the first *spoken* token, not just the first token: reasoning tokens are silent (C-013)
- [ ] 2.7 Latency budget: split 800 ms across stages and mark which stage is over budget
- [ ] 2.8 Measure *true* speech end with Silero VAD instead of "end of the audio file" (C-016), so speech end → final excludes trailing silence in the clip
- [ ] 2.9 Track connect time and network round trip per provider as separate metrics (C-009); check whether Deepgram offers an endpoint closer to India

**Exit:** baseline P50/P95 recorded. You can point at the slowest stage with evidence.
**Signals to:** Vapi, Retell, Pipecat, LiveKit, Future AGI, Roark.

## Phase 3: Provider adapters (own core)

**Goal:** our own STT/TTS adapters in `swar.core`, connected to Pipecat through one processor (D-005).
**Learn first:** L-007 adapter pattern & resilience.

- [ ] 3.1 Design the `STTProvider` / `TTSProvider` interfaces (audio in, typed events out; connect / close; latency stats). Record as a decision
- [ ] 3.2 Sarvam STT adapter (raw WebSocket)
- [ ] 3.3 Deepgram STT adapter
- [ ] 3.4 Sarvam Bulbul and Cartesia TTS adapters
- [ ] 3.5 `SwarSTT` / `SwarTTS` Pipecat processors that wrap the adapters. The agent runs on them with identical behaviour to the baseline
- [ ] 3.6 Contract tests: the same WAV through every adapter produces events in the expected order (recorded fixtures, no live calls)
- [ ] 3.7 Normalise output: script (Devanagari vs Latin), punctuation, timestamps, confidence
- [ ] 3.8 GitHub Actions: ruff + pytest on every push

**Exit:** the provider is a config value; contract tests green in CI.
**Signals to:** Bolna, Vapi, Retell, Pipecat.
**Stretch:** upstream a fix or improvement to Pipecat (e.g. found while building 3.2–3.5). This is the strongest single signal for Daily.

## Phase 4: Mini Indic benchmark

**Goal:** routing decisions come from data, not opinion. **First public artifact.**
**Learn first:** L-008 WER/CER & Indic text normalisation.

- [ ] 4.1 Test set: about 30–50 clips per mix (Hinglish, Tamil-English, Bengali-English) from your own and friends' recordings, public code-switched datasets (check licences), and TTS-generated clips (tagged separately). Ground-truth transcripts (C-004)
- [ ] 4.2 Two versions of every clip: **browser quality** (16 kHz, light noise) and **phone quality** (8 kHz, μ-law round trip, noise such as traffic, TV, crowd, fan at several SNRs). The demo is browser-only, but phone audio is the hard case target companies live with
- [ ] 4.3 Runner: every STT × every clip → transcript + time-to-first-partial + time-to-final. Cache results in Postgres
- [ ] 4.4 Scoring with jiwer: WER, CER, code-switch-span WER, wrong-script rate (normalise first)
- [ ] 4.5 Results tables + charts → `configs/routing.yaml` (language mix → ranked providers)
- [ ] 4.6 Write-up: "Which STT handles Indian code-switching on browser and phone audio?" Publish it

**Exit:** routing table generated from benchmark results. ← **v0 milestone**
**Signals to:** Sarvam, Gnani, Smallest, Deepgram, Bolna, KugelAudio.

## Phase 5: Router v1: language routing + failover

**Goal:** route per language mix, survive provider failures, and measure the *naive* switch cost.
**Learn first:** L-007 resilience patterns.

- [ ] 5.1 Language ID v1 from partial transcripts (script + word-list heuristics); accuracy on the test set
- [ ] 5.2 Language ID v2: an audio language-ID model on the first 300–500 ms; compare accuracy against ms of audio needed; pick one (record a decision) (C-003)
- [ ] 5.3 Naive routing: switch provider on the next turn; **measure the overhead (the "before" number)**
- [ ] 5.4 Health scores: rolling time-to-first-byte P95 + error rate per provider
- [ ] 5.5 Per-provider timeouts + circuit breaker (closed / open / half-open)
- [ ] 5.6 Hedged requests for LLM and TTS when the first-byte budget is exceeded
- [ ] 5.7 Fault injector: an adapter wrapper that adds delay / errors / disconnects on a schedule
- [ ] 5.8 Chaos test: kill a provider mid-call; measure recovery time and dead air

**Exit:** naive switch cost and failover recovery measured.
**Signals to:** Bolna, Vapi, Retell, Exotel.

## Phase 6: Fast switching (the core)

**Goal:** a provider switch adds < 50 ms and loses 0 words.

- [ ] 6.1 Audio ring buffer (last N seconds of frames) with unit tests
- [ ] 6.2 Replay on switch: the new provider receives buffered audio; dedupe the transcript at the seam; measure words lost
- [ ] 6.3 Warm connection pool: keep likely providers' streams open, with keepalive; measure the cost of idle connections
- [ ] 6.4 Sticky routing with hysteresis; measure the flip-flop rate
- [ ] 6.5 Speculative dual-streaming while uncertain; keep the winner, cancel the loser cleanly; measure the extra cost
- [ ] 6.6 Per-call priors: greeting turn, browser language setting, user-profile language field (phone-number region added in 12.5)
- [ ] 6.7 One consistent multilingual TTS voice per call
- [ ] 6.8 Paired measurement of switch cost: naive (5.3) vs Swar (C-007)

**Exit:** the headline chart: naive vs Swar switch cost. ← **v1 milestone**
**Signals to:** everyone. This is the project's headline result.

## Phase 7: Eval harness

Comes before turn-taking so that turn-taking work ships with numbers.

- [ ] 7.1 Scenario format (YAML): persona, language mix, script beats, expected outcome
- [ ] 7.2 Audio caller: plays clips into the agent over the real transport with realistic timing
- [ ] 7.3 LLM-driven AI callers (LLM + TTS): impatient, pauses mid-sentence, switches language, says "haan haan", interrupts
- [ ] 7.4 LLM judge with a rubric, plus hard checks (does the booking row exist in Postgres?)
- [ ] 7.5 `make eval`: runs the suite and writes a markdown report + charts with the **7 README metrics, baseline vs Swar**
- [ ] 7.6 GitHub Actions: reduced suite on PRs touching routing / turn detection / prompts; fail on a P95 or task-success regression
- [ ] 7.7 Call replay: re-run a recorded call against a new agent version

**Signals to:** Hamming, Cekura, Roark, Coval, Bluejay, Future AGI (the whole testing category).

## Phase 8: Turn-taking

- [ ] 8.1 Baseline: false cut-off and missed barge-in rates with Silero VAD only
- [ ] 8.2 Evaluate Smart Turn on Hinglish before building anything (D-011)
- [ ] 8.3 Tune for Hinglish hesitation pauses ("matlab...", "woh..."), with a small set of incomplete utterances
- [ ] 8.4 Backchannel classifier: "haan" / "hmm" vs real interruption. On a real interruption, trim the LLM context to what was actually spoken
- [ ] 8.5 Report: false cut-off %, missed barge-in %, backchannel accuracy (baseline vs Swar)

**Signals to:** Vapi, Retell, Pipecat, LiveKit, Sarvam, Wavelength.

## Phase 9: Tools, filler speech, the real task

- [ ] 9.1 Postgres schema: clinics, slots, bookings, EMI accounts
- [ ] 9.2 Tool calls: `check_slots`, `book_slot`, `lookup_customer`
- [ ] 9.3 Filler speech when a tool exceeds about 300 ms, without double-speaking
- [ ] 9.4 Grounding: the agent may only state dates and amounts that came from tool results (hallucination check in evals)
- [ ] 9.5 Context management: summarise older turns, keep the prompt short
- [ ] 9.6 EMI-reminder script where the agent speaks first (in the browser; real outbound calls come in 12.3)

**Signals to:** GreyLabs, Skit, Ringg, Edesy, Callab.

## Phase 10: Scale, cost & public deployment

- [ ] 10.1 Deploy with Docker Compose on one VM in an India region (D-012); compare latency against running locally (C-009)
- [ ] 10.2 Make the browser demo reachable from anywhere: HTTPS (browsers only allow the mic on secure pages) + a TURN server so WebRTC works behind home/office NATs and firewalls (C-011)
- [ ] 10.3 Load generator: N concurrent AI callers
- [ ] 10.4 Calls per worker before P95 degrades; measure event-loop lag
- [ ] 10.5 Backpressure and graceful degradation under overload
- [ ] 10.6 Redis for live call state; run more than one worker (D-010)
- [ ] 10.7 Cost per call minute, including speculative streaming: baseline vs Swar

**Signals to:** Vapi, Retell, LiveKit, Deepgram, Bolna.

## Phase 11: Ship the browser demo

- [ ] 11.1 Demo page: Pipecat's prebuilt browser client + a live per-turn latency panel (the one custom view D-009 allows)
- [ ] 11.2 Rewrite the README with measured results in place of targets
- [ ] 11.3 Demo video: one browser call switching Tamil-English → Hinglish, with a provider failure injected and the latency timeline on screen
- [ ] 11.4 Technical write-ups (benchmark, switching, turn-taking)
- [ ] 11.5 Per-company pitch: which part of Swar maps to their product (see table below)

**Exit:** anyone with the link can talk to Swar in their browser. ← **v2 milestone**

## Phase 12: Phone numbers (later, after the browser demo)

Deferred by D-013. The core work doesn't depend on it; it adds the real phone path.

- [ ] 12.1 Choose the provider for an Indian number (Exotel or Twilio India) and check whether KYC works for an individual (C-010). **Start this enquiry during Phases 4–5** so it isn't blocking later
- [ ] 12.2 Phone audio into the agent: telephony WebSocket → Pipecat (8 kHz μ-law)
- [ ] 12.3 Real outbound calls (EMI reminders); call recordings to object storage
- [ ] 12.4 Re-run the benchmark on real phone audio. Was the simulated 8 kHz audio realistic?
- [ ] 12.5 Add the caller's phone-number region as a routing prior (extends 6.6)

**Signals to:** Exotel, Callab, Retell, Vapi, Bolna.

---

## Company targeting: does this cover all 25?

**Short answer:** the project touches all three categories in the README, but the fit isn't equal.
About 20 companies are a strong fit if the matching phases are done well. A few need a stretch task,
or need you to frame the project differently.

| Group | Fit | What they'll look at | Phases that matter |
|---|---|---|---|
| **Bolna, Sarvam, Smallest, Gnani** | Strong | Indic code-switching quality, the benchmark, routing across Indian providers | 3, 4, 5, 6 |
| **Skit, GreyLabs, Ringg, Edesy** | Strong | A real task completed reliably (booking, EMI), telephony, evals | 7, 9, 10 |
| **Exotel, Callab** | Medium until Phase 12 | Telephony and phone integration come after the browser demo; the 8 kHz benchmark and failover still count | 4, 5, 12 |
| **Hamming, Cekura, Roark, Coval, Bluejay, Future AGI** | Strong, **only if Phase 7 is serious** | AI callers, LLM judge, regression in CI, chaos tests, call replay | 2, 5.7–5.8, 7 |
| **Vapi, Retell** | Strong | Latency engineering, turn-taking, failover, concurrency | 2, 6, 8, 10 |
| **Pipecat / Daily** | Strong (we build on Pipecat) | Deep use of the framework, ideally an upstream contribution | 0.6, 3 + stretch, 8 |
| **LiveKit** | Medium | Realtime/latency skills transfer; the core doesn't depend on Pipecat, so it could be connected to LiveKit Agents | 2, 6, 8 |
| **Deepgram, Cartesia, ElevenLabs** | Medium | Expert, latency-aware use of their API and an honest benchmark. Relevant to solutions / applied / DevRel roles more than model research | 3, 4, 6 |
| **KugelAudio** | Weak as is | On-prem multilingual models. **Stretch:** add a self-hosted open-source Indic STT model as a provider and benchmark it | 4 + stretch |
| **Wavelength** | Weak as is | A consumer companion: naturalness, turn-taking, persona. Routing matters less. Lead with Phase 8 | 8 |

**Takeaways:**

1. The **eval harness (Phase 7) can't be cut**. Six of the 25 companies are testing companies.
2. Building on **Pipecat** makes the project a strong signal to Daily. The **framework-independent core (D-005)** keeps the LiveKit story open.
3. A **self-hosted model adapter** (stretch) improves the fit with KugelAudio, Gnani and Smallest.
4. Check that each company is still hiring before tailoring a pitch (the list is a snapshot).
