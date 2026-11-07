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

## C-004: Realistic test audio with ground truth is scarce
- **Date:** 2026-11-06 · **Phase / task:** plan 4.1 · **Raised by:** Claude · **Status:** Open
- **Problem:** we need noisy, 8 kHz, code-mixed audio with accurate transcripts, for three language mixes.
- **Trade-offs:**
  - TTS-generated audio is cheap but clean and synthetic. It may favour TTS-like speech and flatter some providers.
  - Your own and friends' recordings are realistic but slow to collect, and covering Tamil and Bengali needs native speakers.
  - Public code-switching datasets exist, but licences and recording conditions vary.
- **Mitigation:** mix the sources, tag every clip by source, report results per source, and re-check against real phone audio in plan 10.4.

## C-005: The frameworks may already ship provider fallback
- **Date:** 2026-11-06 · **Phase / task:** plan 0.7 · **Raised by:** Claude · **Status:** Open
- **Problem:** voice frameworks have added fallback / service-switching features (for example, LiveKit Agents has fallback adapters for STT/TTS). An interviewer at LiveKit or Daily will ask: *"How is this different from what we already ship?"*
- **Action:** in plan 0.7, read exactly what exists and write down the gap. Likely differentiators: **language-aware** routing (not just failure-based), switching *mid-utterance* with replay and 0 lost words, health scores based on latency rather than only errors, and the measured < 50 ms overhead.

## C-006: Provider cost and free-credit limits
- **Date:** 2026-11-06 · **Phase / task:** plan 0.3, 6.5, 11.5 · **Raised by:** Claude · **Status:** Open
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
- **Date:** 2026-11-07 · **Phase / task:** plan 2.7, 11.1 · **Raised by:** Claude · **Status:** Open
- **Problem:** providers' servers are in different regions. Every streaming round trip from the agent to a far-away provider adds latency that no code optimisation can remove, and it differs per provider, which skews the benchmark too.
- **Approach:** measure the network round trip to each provider separately from processing time (2.7). Deploy in an India region (D-012) and compare against local runs (11.1). Report benchmark latency together with where it was measured from.

## C-010: Getting an Indian phone number
- **Date:** 2026-11-07 · **Phase / task:** plan 10.2 · **Raised by:** Claude · **Status:** Open
- **Problem:** Indian numbers (Exotel, or Twilio India) require regulatory and business KYC paperwork, which may not be possible for an individual. A foreign Twilio number works but costs Indian testers international calling.
- **Approach:** Twilio first (D-007); start the Exotel enquiry during Phase 4–5 so it isn't blocking later. The browser (WebRTC) demo works regardless.
