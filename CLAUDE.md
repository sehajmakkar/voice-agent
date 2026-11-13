# CLAUDE.md — Swar

## What this project is

**Swar** is a realtime voice agent for Indian callers (clinic booking / EMI reminders) with a
**reliability and orchestration layer** on top. The agent itself is the vehicle; the layer is the product:

- **Language-aware routing:** detect the caller's language mix (Hinglish, Tamil-English, Bengali-English)
  and send audio to the STT/TTS provider that handles that mix best and is fastest right now.
- **Fast switching:** change providers mid-call with < 50 ms added latency and 0 words lost
  (warm connections, audio replay buffer, speculative streaming, hysteresis).
- **Pre-emptive failover:** health scores, timeouts, circuit breakers and hedged requests so a slow
  provider never turns into dead air.
- **Natural turn-taking:** semantic end-of-turn and a backchannel classifier ("haan haan" ≠ interruption).
- **Every turn traced, every feature measured:** the 7 README metrics, always reported as
  **baseline (single provider, no routing) vs Swar** (D-003).

The owner is **Sehaj**. It's a learning and portfolio project aimed at voice-AI companies
(see the README's target list). The build should teach the concepts, and the write-ups should prove them.

## Project docs (keep these current, which is part of every task)

| File | Purpose |
|---|---|
| `README.md` | Public pitch, written in plain language. Replace targets with measured numbers as phases complete. |
| `plan.md` | Phased build plan with small tasks. **Source of truth for what's next.** |
| `decisions.md` | Every lasting technical decision: options, choice, trade-offs (ADR-lite). |
| `challenges.md` | Problems hit or raised, how they were resolved, trade-offs accepted. |
| `learnings.md` | Concepts to learn, brief explanation, interview questions, references. |

### When to write to each file

- **plan.md:** tick a task when it's done (add the commit hash). Add newly discovered tasks under the
  right phase. Never delete a task; strike it through (`~~...~~`) and give the reason.
  Keep the "Current phase" line at the top accurate.
- **decisions.md:** add an entry whenever we pick between two or more reasonable options and the choice will
  last (library, interface shape, data model, threshold, metric definition, infra).
  New entries are **Proposed** until Sehaj confirms. Then they're **Accepted**. Never rewrite an
  accepted decision. Add a new one that **supersedes** it.
- **challenges.md:** add an entry when something non-trivial goes wrong or a real tension shows up:
  a bug that took > 30 min, surprising provider behaviour, a design conflict, a risk, or anything
  Sehaj raises. Record who raised it, the options, the trade-off, and the resolution.
- **learnings.md:** add an entry when a task touches a concept worth being able to explain in an
  interview. Keep it brief: what it is, why it mattered here, 1–3 interview questions, references
  (official docs first).
- **README.md:** keep it simple and non-technical where possible. Don't let metric lists grow back;
  supporting metrics belong in Grafana and plan tasks, not the README.
- Cross-link with IDs: `D-003`, `C-002`, `L-005`, `plan 4.3`.
- At the end of each task, say which of these files were updated, or "docs: no update needed".

## How to work with Sehaj

- Sehaj is learning this domain. Before implementing a core concept (streaming, cancellation, ring
  buffer, circuit breaker, ...), explain it in a few sentences and say why it matters. Point out
  moments that are likely interview material.
- Work in small, reviewable steps that map to `plan.md` tasks. Propose before making large or
  structural changes.
- Be honest about trade-offs and about results that miss targets. A missed target that's measured
  and explained is worth more than an unmeasured claim.
- Don't mark a new decision Accepted, or a phase complete, without Sehaj's confirmation.

## Engineering principles

1. **Every feature ships with a number.** No feature is done until its metric is measured against the baseline.
2. **Measure before optimising.** Tracing and the baseline come before the router and switching work (D-006).
3. **Latency is reported as P50 / P95 / P99**, per language mix and per provider. Never only averages.
4. **`swar.core` never imports Pipecat** (D-005). Router, adapters, buffers and health scores are plain
   asyncio. Pipecat glue lives only in `swar.pipeline`.
5. **Providers are only accessed through adapters.** No provider SDK or WebSocket calls outside `swar/core/providers/`.
6. **The baseline config (`configs/baseline.yaml`) is frozen** once Phase 1 is done. Never change it; add new configs.
7. **Async everywhere, cancellation-safe.** Interruptions cancel in-flight LLM/TTS work cleanly;
   never block the event loop (CPU-heavy work goes to a thread or process).
8. **No live API calls in unit tests or CI.** Use recorded fixtures. Live calls only in benchmark/eval runs.
9. **No secrets in git.** Keys live in `.env` (gitignored); `.env.example` lists the names.

## Stack (final, see decisions.md)

| Layer | Choice |
|---|---|
| Language | Python 3.12 + asyncio (D-002) |
| Voice pipeline | Pipecat (D-004) |
| Transport | Browser only via SmallWebRTC, including the public demo; phone numbers in Phase 12 (D-013) |
| Server | FastAPI (D-010) |
| STT | Sarvam, Deepgram (+ Smallest / Gnani if access) (D-008) |
| TTS | Sarvam Bulbul, Cartesia (D-008) |
| LLM | Gemini Flash primary, Sarvam LLM fallback; exact model IDs pinned (D-015) |
| VAD / turn | Silero VAD, Smart Turn (D-011) |
| Storage | Postgres (SQLAlchemy 2.0 async + Alembic), Redis from Phase 10 (D-010) |
| Observability | OpenTelemetry → Jaeger, Postgres → Grafana (D-009) |
| Evals | jiwer, pytest, LLM judge, GitHub Actions |
| Infra / tooling | Docker Compose on one India-region VM; uv, ruff, pytest-asyncio, pre-commit (D-012) |

## Repo layout (planned, created in plan 0.2)

```
src/swar/
  core/            # framework-independent, never imports Pipecat
    providers/     #   stt/, tts/: our own adapters behind one interface
    router/        #   language ID, health scores, failover, switching
    audio/         #   ring buffer, resampling, μ-law
  pipeline/        # Pipecat glue: SwarSTT / SwarTTS processors, bot assembly
  turn/            # turn detection, backchannel classifier
  agent/           # prompts, tools, filler speech
  tracing/         # OpenTelemetry setup, turn metrics
  server.py        # FastAPI: WebRTC signalling (telephony webhooks in Phase 12)
configs/           # baseline.yaml (frozen), routing.yaml, ...
scripts/           # dev tools and playgrounds (output goes to out/, gitignored)
bench/             # mini Indic STT benchmark
evals/             # scenarios, AI callers, judge, `make eval`
infra/             # docker-compose, Grafana dashboards
tests/
```

## Commands

```bash
make install   # uv sync + install the git pre-commit hook
make check     # lint + tests: what CI runs. Run before every commit
make test      # uv run pytest   (single test: uv run pytest tests/test_config.py -k name)
make format    # ruff auto-fix + format
make up        # Postgres :5432 · Jaeger UI :16686 (OTLP :4317) · Grafana :3000 (admin/admin)
make down      # stop infra (data kept in Docker volumes)
cp .env.example .env   # then add API keys
uv run python scripts/audio_playground.py --record 5 --play   # hear what phone audio does
uv run python scripts/stream_stt.py --input out/clips/hinglish_booking_16k.wav   # live STT, both providers
uv run python scripts/parrot_bot.py   # Pipecat parrot bot → open http://localhost:7860 (headphones)
```

- Add dependencies with `uv add <pkg>` (or `uv add --dev <pkg>`), never `pip install`. Commit `uv.lock`.
- Settings come from `swar.config.get_settings()`. Use `settings.require("deepgram_api_key")` for a
  clear error when a key is missing.
- Pipecat is 1.x (D-017): `PipelineWorker` + `WorkerRunner`, `VADProcessor`, `create_transport`. Check the installed
  source (`.venv/lib/python3.12/site-packages/pipecat/`) before writing Pipecat code; most online examples are 0.0.x.
- Test Pipecat processors with `pipecat.tests.utils.run_test` (see `tests/pipeline/`).
- Architecture rules are enforced as tests in `tests/test_architecture.py`. Add a test when adding a rule.
- Running the agent and `make eval` are added in Phases 1 and 7.
