# Challenges

Problems hit or raised while building Swar, how we resolved them, and the trade-offs accepted.
Good interview material: "tell me about a hard problem you solved" answers come from here.

**Status:** `Open` · `Resolved` · `Accepted risk` (known, consciously not fixed)
**Raised by:** Sehaj · Claude · Found while building

### Template

```
## C-000: Title
- **Date:** YYYY-MM-DD · **Phase / task:** plan x.y · **Raised by:** ... · **Status:** Open
- **Problem:** what happened / what's hard
- **Why it's hard:** the underlying reason
- **Options & trade-offs:** ...
- **Resolution:** what we did (and the numbers, if measured)
- **Lesson:** one line you'd say in an interview
- **Links:** D-xxx, L-xxx
```

---

## C-001: The README has three conflicting eval sections
- **Date:** 2026-11-06 · **Phase / task:** plan 0.1 · **Raised by:** Claude (Sehaj: "too many evals and metrics") · **Status:** Resolved 2026-11-07
- **Problem:** three "Evals & metrics" sections with different targets: turn latency P50 < 600 ms vs < 800 ms, dead air < 1% vs < 2%, task completion > 85% vs > 90%, false cut-off < 3% vs < 5%. The roadmap also listed the eval harness three times.
- **Why it matters:** an interviewer reading the README sees inconsistent claims, and the eval harness can't be built against three specs.
- **Options & trade-offs:** see D-003.
- **Resolution:** README rewritten in plain language with **7 headline metrics** (each a question the metric answers). Supporting metrics (flip-flop rate, wrong-script rate, per-stage TTFB, ...) moved to Grafana and plan tasks. One roadmap table that matches plan.md.
- **Lesson:** a metric belongs in the headline only if it proves a claim the project makes.

## C-002: The scope is very large for one person
- **Date:** 2026-11-06 · **Phase:** all · **Raised by:** Claude · **Status:** Accepted risk
- **Problem:** the roadmap covers about 13 substantial systems (pipeline, adapters, tracing, benchmark, router, switching, turn-taking, tools, telephony, evals, CI, load testing, demo).
- **Risk:** the project never reaches a showable state.
- **Mitigation:** milestones with cut lines in plan.md (v0 after Phase 4 is already apply-ready). Each phase produces something demoable on its own.

## C-003: Early language ID on code-mixed speech is hard
- **Date:** 2026-11-06 · **Phase / task:** plan 5.1–5.2 · **Raised by:** Claude · **Status:** Open
- **Problem:** "Hinglish" isn't a label a standard LID model outputs. A Hinglish speaker is Hindi + English *within one sentence*, so per-utterance LID flips between them. Separating Tamil-English from Hinglish (different base languages) is much easier than Hindi vs Hinglish.
- **Why it's hard:** 300–500 ms of audio is often one or two words; code-switch points are unpredictable; 8 kHz noise hurts.
- **Reframe to consider:** the routing question isn't "which language?" but "which provider will transcribe this best?". The decision may only need the *base* Indic language plus a code-mixing flag.
- **Options:** transcript heuristics (script + lexicon), audio LID models, priors (region, greeting turn), speculative streaming when unsure. Plan 5.1 vs 5.2 measures this.
- **Evidence (plan 0.5, 2026-11-10):** in both runs, Deepgram's first partial for "हाँ जी" was tagged **Persian (`fa`)** and partly written in Arabic script; it corrected itself to Hindi one second later. Language tags from the first ~1 s of partials can't be trusted on their own. Also, Sarvam sends no partials at all (C-014), so transcript-based early language ID only works with some providers.

## C-004: Realistic test audio with ground truth is scarce
- **Date:** 2026-11-06 · **Phase / task:** plan 4.1 · **Raised by:** Claude · **Status:** Open
- **Problem:** we need noisy, 8 kHz, code-mixed audio with accurate transcripts, for three language mixes.
- **Trade-offs:**
  - TTS-generated audio is cheap but clean and synthetic. It may favour TTS-like speech and flatter some providers.
  - Your own and friends' recordings are realistic but slow to collect, and covering Tamil and Bengali needs native speakers.
  - Public code-switching datasets exist, but licences and recording conditions vary.
- **Mitigation:** mix the sources, tag every clip by source, report results per source, and re-check against real phone audio in plan 12.4.

## C-005: The frameworks may already ship provider fallback
- **Date:** 2026-11-06 · **Phase / task:** plan 0.7 · **Raised by:** Claude · **Status:** Open
- **Problem:** voice frameworks have added fallback / service-switching features (for example, LiveKit Agents has fallback adapters for STT/TTS). An interviewer at LiveKit or Daily will ask: *"How is this different from what we already ship?"*
- **Action:** in plan 0.7, read exactly what exists and write down the gap. Likely differentiators: **language-aware** routing (not just failure-based), switching *mid-utterance* with replay and 0 lost words, health scores based on latency rather than only errors, and the measured < 50 ms overhead.

## C-006: Provider cost and free-credit limits
- **Date:** 2026-11-06 · **Phase / task:** plan 0.3, 6.5, 10.7 · **Raised by:** Claude · **Status:** Open
- **Problem:** benchmarks (every provider × every clip × several noise levels), speculative dual-streaming (roughly double STT cost during uncertainty), warm idle connections and synthetic-caller evals all burn credits.
- **Mitigation:** record a credits/limits table in 0.3, cache benchmark results (never re-transcribe the same clip+provider+config), use small eval suites in CI, and report the cost of speculation honestly (metric 8).

## C-007: Measuring a < 50 ms difference inside noisy turn latency
- **Date:** 2026-11-06 · **Phase / task:** plan 5.3, 6.8 · **Raised by:** Claude · **Status:** Open
- **Problem:** turn latency varies by hundreds of ms between turns (LLM and network jitter). Comparing "turns with a switch" against "turns without" across live calls can't reliably detect a 50 ms difference without a very large sample.
- **Approach:** measure switch overhead in a **controlled, paired** setup: the same audio played with and without a forced switch, many repetitions. Report the median difference with a confidence interval, and measure the STT stage on its own, not the whole turn.
- **Lesson:** design the measurement before the optimisation.

## C-008: Pipecat's built-in STT services can't do cross-provider switching
- **Date:** 2026-11-07 · **Phase / task:** plan 3.1 · **Raised by:** Claude · **Status:** Resolved (by design, D-005)
- **Problem:** each built-in Pipecat STT/TTS service opens and owns its own provider connection. Warm pools, replaying buffered audio into a *different* provider, and speculative dual-streaming all need one component that controls several provider connections at once.
- **Options & trade-offs:** switch between built-in services (little code, but every switch pays connection setup and loses in-flight audio) · write our own adapters in a framework-independent core, behind one Pipecat processor (more code per provider, full control).
- **Resolution:** our own adapters in `swar.core`. The Phase 1 baseline still uses the built-in services, which makes it a fair "off-the-shelf" comparison.
- **Lesson:** use the framework for the plumbing, and own the part that is your actual product.

## C-009: Network distance to providers eats the latency budget
- **Date:** 2026-11-07 · **Phase / task:** plan 2.7, 10.1 · **Raised by:** Claude · **Status:** Open
- **Problem:** providers' servers are in different regions. Every streaming round trip from the agent to a far-away provider adds latency that no code optimisation can remove, and it differs per provider, which skews the benchmark too.
- **Measured (plan 0.5, 2026-11-10, from Sehaj's machine in India):** TCP connect to `api.deepgram.com` took ~280–400 ms (one round trip, which suggests US servers); to `api.sarvam.ai` (AWS Mumbai IP range) ~40 ms. A new WebSocket needs 3–4 round trips, so **Deepgram's connect took 0.9–1.4 s vs Sarvam's ~160 ms**. Every result message from Deepgram also arrives ~150 ms later (one-way delay). This makes the case for warm connections (6.3) and an India-region deployment, and it biases any latency comparison towards Sarvam when measured from India.
- **Approach:** measure the network round trip to each provider separately from processing time (2.7, 2.9). Deploy in an India region (D-012) and compare against local runs (10.1). Report benchmark latency together with where it was measured from.

## C-010: Getting an Indian phone number
- **Date:** 2026-11-07 · **Phase / task:** plan 12.1 · **Raised by:** Claude · **Status:** Deferred (D-013)
- **Problem:** Indian numbers (Exotel, or Twilio India) require regulatory and business KYC paperwork, which may not be possible for an individual. A foreign Twilio number works but costs Indian testers international calling.
- **Approach:** 2026-11-10: Sehaj moved phone numbers after the browser demo (D-013), so this is off the critical path. Still start the Exotel / Twilio India KYC enquiry during Phases 4–5 so it's ready when Phase 12 starts.

## C-011: A public browser demo needs HTTPS and a TURN server
- **Date:** 2026-11-10 · **Phase / task:** plan 10.2 · **Raised by:** Claude · **Status:** Open
- **Problem:** browsers only allow microphone access on HTTPS pages (or localhost). And peer-to-peer WebRTC from a visitor's browser to our VM often fails behind home routers, office firewalls and mobile networks (NAT), so it works on localhost and then breaks for real users.
- **Options & trade-offs:** run our own TURN server (coturn; free, but one more thing to operate and it relays audio, which adds a hop) · a managed TURN service (simple, small cost) · switch the public demo to a hosted WebRTC provider such as Daily (most reliable, adds an account, ties the demo to that service).
- **Approach:** decide in 10.2. Measure how much latency the TURN relay adds when it's in use.

## C-012: Sarvam account has no credits; model IDs get deprecated
- **Date:** 2026-11-10 · **Phase / task:** plan 0.3 · **Raised by:** found while verifying keys · **Status:** Resolved 2026-11-10 (credits added; all Sarvam APIs verified)
- **Problem:** the Sarvam key is valid, but every paid call returns `402 insufficient_quota_error: No credits available`. Sarvam is the Indian-language specialist in the routing design, so this blocks the Sarvam part of 0.5, the Sarvam adapters (3.2, 3.4) and half of the benchmark (Phase 4). Separately, the LLM model `sarvam-m` has been deprecated in favour of `sarvam-105b`.
- **Not blocked:** 0.4, Deepgram streaming in 0.5, 0.6, and all of Phases 1–2 (the baseline can run on Deepgram + Gemini + Cartesia).
- **Lesson:** providers deprecate model IDs without warning. Pin IDs in config, and let the contract tests (3.6) fail loudly when a model disappears.

## C-013: Reasoning LLMs add silent latency before the first spoken word
- **Date:** 2026-11-10 · **Phase / task:** plan 2.6, D-015 · **Raised by:** found while verifying Sarvam · **Status:** Open
- **Problem:** `sarvam-105b` is a reasoning model. On a one-line Hinglish question, 156 of its 219 output tokens were hidden reasoning, and the whole reply took 1.14 s. In a voice agent, reasoning tokens are pure dead air: the caller hears nothing until the first *answer* token reaches TTS. Its reply was also in a formal, Urdu-heavy register ("makhsoos auqaat", "barah-e-raast") rather than everyday Hinglish.
- **Why it matters:** "time to first token" from the API can look fast while the time to the first *spoken* token is slow. Reasoning models are also a poor fit as a *fallback*, which is supposed to rescue a slow turn.
- **Options:** turn reasoning off or down if the API allows it · use a non-reasoning model for the fallback · keep Sarvam's LLM for non-realtime work (judging, summarising) only.
- **Next step:** measure it properly in 2.6; revisit D-015 with the numbers. Register and language style are handled by the voice prompt (1.2).

## C-014: Sarvam streaming sends no partial transcripts
- **Date:** 2026-11-10 · **Phase / task:** plan 0.5 · **Raised by:** found while building · **Status:** Open (design input for Phases 5, 6, 8)
- **Problem:** Deepgram streams partial transcripts every ~1 s while the caller speaks. Sarvam sends nothing until its own voice detector decides the caller paused, then sends the finished segment. In our clip, Sarvam's first text arrived ~6 s after speech started.
- **Why it matters:** three planned features depend on partials: early language ID from transcripts (5.1), semantic end-of-turn using the partial transcript (8.2), and starting the LLM early. None of these work on Sarvam's stream alone.
- **Options & trade-offs:** use audio-based language ID instead of transcript-based (5.2) · run a cheap partial-producing provider alongside Sarvam during uncertainty (speculative streaming, 6.5; costs more) · accept that Sarvam turns get a less informed end-of-turn decision.
- **Next step:** the provider interface (3.1) must expose whether a provider produces partials, so the router and turn controller can adapt.

## C-015: Language-ID tags and script are unstable in early partials
- **Date:** 2026-11-10 · **Phase / task:** plan 0.5, 4.3 · **Raised by:** found while building · **Status:** Open
- **Problem:** see the C-003 evidence: first partial tagged Persian in Arabic script, then corrected. Also "दस" vs "10" for the same audio across two runs (Deepgram `smart_format`). Same audio, different text, so benchmarks need several runs per clip and text normalisation before scoring (L-008).

## C-016: "Speech end" was measured as the end of the file, not the end of speech
- **Date:** 2026-11-10 · **Phase / task:** plan 0.5 → 2.8 · **Raised by:** Claude · **Status:** Open
- **Problem:** the "speech end → final" numbers in 0.5 treat the last frame of the clip as the moment speech ended. TTS clips carry a little trailing silence, so speech really ended earlier and the true latency is somewhat *higher* than reported.
- **Fix:** in Phase 2, take speech end from Silero VAD on our side (the same signal the agent uses), not from the file length.
