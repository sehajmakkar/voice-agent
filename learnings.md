# Learnings

Concepts to understand while building Swar: what each one is, why it mattered here, interview
questions it prepares you for, and where to read more (official docs first).

**Status:** `[ ]` to learn · `[~]` learning · `[x]` can explain it without notes

### Template

```
## L-000: Concept  `[ ]`
- **Phase / task:** plan x.y
- **What it is:** 2–4 sentences
- **Why it mattered in Swar:** the concrete place it showed up
- **Interview questions:** 1–3
- **References:** links
```

---

## L-001: Digital audio basics: PCM, sample rate, frames, μ-law  `[ ]`
- **Phase / task:** plan 0.4
- **What it is:** PCM is raw audio as a series of amplitude samples. *Sample rate* is samples per second (phone = 8 kHz, most STT models = 16 kHz). *Bit depth* is bits per sample (usually 16-bit). Audio is streamed in small *frames* (often 20 ms). μ-law compresses 16-bit samples to 8 bits; it's the telephony standard.
- **Why it mattered:** phone audio is 8 kHz μ-law, so it loses everything above about 4 kHz, which hurts consonants and STT accuracy. Wrong sample-rate assumptions are the #1 cause of "the STT returns garbage".
- **Interview questions:**
  - How many bytes is a 20 ms frame of 16 kHz, 16-bit mono PCM? *(320 samples × 2 bytes = 640 bytes)*
  - Why does phone audio hurt STT accuracy, and what can you do about it?
  - Should you resample 8 kHz → 16 kHz before sending to an STT trained on 16 kHz?
- **References:** Twilio Media Streams docs (audio format) · Wikipedia: μ-law algorithm, Nyquist–Shannon sampling theorem

## L-002: The streaming voice pipeline  `[ ]`
- **Phase / task:** plan 1.1
- **What it is:** STT streams *partial* transcripts and then a *final*. The LLM streams tokens. Tokens are grouped into sentences/phrases and sent to TTS, which streams audio chunks back. Every stage starts before the previous one finishes; that overlap is where latency is won.
- **Why it mattered:** turn latency = end of speech → first audio byte, not total processing time. Speech-to-speech vs pipeline is D-001.
- **Interview questions:**
  - Walk me through everything that happens between the caller stopping speaking and the agent's first audio.
  - Why chunk LLM output by sentence before TTS, not by token or by full reply?
  - When would you choose a speech-to-speech model over a cascaded pipeline?
- **References:** Pipecat docs (docs.pipecat.ai) · LiveKit Agents docs (docs.livekit.io/agents)

## L-003: VAD vs end-of-turn detection  `[ ]`
- **Phase / task:** plan 1.3, Phase 8
- **What it is:** VAD (voice activity detection) answers "is someone speaking *right now*?". End-of-turn detection answers "have they *finished* their thought?". Silence alone is a poor signal: people pause mid-sentence, especially in Hinglish ("matlab... woh...").
- **Why it mattered:** too short a silence threshold cuts callers off; too long adds dead latency to every turn. A semantic model uses meaning plus silence to get both.
- **Interview questions:**
  - Why isn't silence-based endpointing enough? What's the trade-off in the silence threshold?
  - How would you tell a backchannel ("haan") from a real interruption?
  - What should happen to a half-spoken agent reply when the caller interrupts?
- **References:** Silero VAD (github.com/snakers4/silero-vad) · Pipecat and LiveKit turn-detection docs

## L-004: asyncio concurrency & cancellation  `[ ]`
- **Phase / task:** plan 0.5, 1.3, 6.5
- **What it is:** one event loop runs many coroutines that take turns at each `await`. Tasks run concurrently; queues connect producers and consumers; cancelling a task raises `CancelledError` inside it so it can clean up. `TaskGroup` gives structured concurrency (child tasks can't outlive the parent).
- **Why it mattered:** a call is many concurrent streams (audio in, STT, LLM, TTS, audio out). Barge-in has to cancel the LLM and TTS instantly without leaking connections. One blocking call (CPU-heavy resampling, a sync SDK) stalls *every* call on that worker.
- **Interview questions:**
  - How do you cancel an in-flight LLM stream and TTS playback on interruption without leaking resources?
  - What happens if you call a blocking function inside a coroutine? How do you find and fix it?
  - Concurrency vs parallelism in Python. When do you need processes?
- **References:** Python docs: asyncio (Tasks, TaskGroup, Queues, cancellation) · PEP 3156

## L-005: Latency percentiles & budgets  `[ ]`
- **Phase / task:** plan 2.5–2.6
- **What it is:** P95 = 95% of requests are faster than this. Averages hide the slow tail, and in voice the tail is what makes callers hang up. A *latency budget* splits the end-to-end target across stages so each stage has a number to hit.
- **Why it mattered:** every Swar metric is P50/P95/P99. Hedged requests and failover exist to cut the tail.
- **Interview questions:**
  - Why report P95/P99 instead of the average?
  - How would you set a latency budget for an 800 ms voice turn?
  - Why does tail latency get worse when a request fans out to several services?
- **References:** Dean & Barroso, "The Tail at Scale" (CACM, 2013)

## L-006: Distributed tracing with OpenTelemetry  `[ ]`
- **Phase / task:** plan 2.2
- **What it is:** a *trace* is one unit of work (a turn); *spans* are timed steps inside it (STT, LLM, TTS), with attributes (provider, language mix). Context propagation links spans across tasks and services.
- **Why it mattered:** the per-turn waterfall that shows which stage was slow, which is the data behind every latency claim.
- **Interview questions:**
  - How would you find which stage made one specific call slow?
  - Traces vs metrics vs logs: what is each good for?
- **References:** opentelemetry.io/docs (Python) · Jaeger docs

## L-007: Resilience patterns: timeouts, circuit breakers, hedging, adapters  `[ ]`
- **Phase / task:** plan 3.1, Phase 5
- **What it is:**
  - *Timeout:* stop waiting.
  - *Circuit breaker:* after repeated failures, stop calling a provider for a while (closed → open → half-open → closed).
  - *Hedged request:* if the first request is slow, send a second one and take whichever answers first.
  - *Adapter pattern:* one interface, many provider implementations, so routing logic never knows provider details.
- **Why it mattered:** this is how Swar turns "provider got slow" into "the caller noticed nothing".
- **Interview questions:**
  - Hedged requests vs retries: what does each cost, and when do you use which?
  - Walk through the circuit breaker states. How do you choose the thresholds?
  - How would you design one interface over STT providers whose streaming APIs all differ?
- **References:** Martin Fowler, "CircuitBreaker" (martinfowler.com/bliki/CircuitBreaker.html) · "The Tail at Scale" (hedging)

## L-008: WER / CER and Indic text normalisation  `[ ]`
- **Phase / task:** plan 4.4
- **What it is:** WER = (substitutions + deletions + insertions) / reference words. CER is the same at character level. Before scoring you must *normalise* text (case, punctuation, numbers, and script: "kal" vs "कल").
- **Why it mattered:** CER is often fairer for Indic languages (word segmentation and spelling vary). Without script normalisation, a provider writing Hindi in Latin script looks "wrong" when it's actually right, so the benchmark (and the routing table built from it) would be misleading.
- **Interview questions:**
  - Why might CER be better than WER for Indic languages?
  - How do you score a transcript that writes Hindi words in Latin script?
  - How would you make sure your benchmark isn't biased towards one provider?
- **References:** jiwer (github.com/jitsi/jiwer) · Indic NLP / transliteration libraries (pick in Phase 4)

## L-009: Pipecat: frames, processors and pipelines  `[ ]`
- **Phase / task:** plan 0.6, 3.5
- **What it is:** in Pipecat, everything that moves through a call is a *frame*: audio chunks, transcripts, LLM tokens, and control signals such as "user started speaking". A *processor* receives frames, acts on them, and pushes frames onward. A *pipeline* is a chain of processors. Frames flow downstream (input → output) and upstream (e.g. errors, interruption signals).
- **Why it mattered:** Swar's router and replay buffer are a custom processor placed in front of STT. Interruptions work by sending frames that make downstream processors cancel their work (D-004, D-005).
- **Interview questions:**
  - How does an interruption propagate through a frame-based pipeline?
  - Why separate data frames from control frames?
  - Where would you put a component that needs to see raw audio *and* transcripts?
- **References:** Pipecat docs (docs.pipecat.ai): core concepts, custom frame processors

## L-010: WebRTC vs WebSockets for realtime audio  `[ ]`
- **Phase / task:** plan 1.1, 10.1
- **What it is:** WebRTC sends audio over UDP, with a jitter buffer, packet-loss handling, echo cancellation and the Opus codec built in. It's designed for live media. WebSockets run over TCP: simple and reliable, but a lost packet stalls everything behind it (head-of-line blocking). Telephony bridges such as Twilio Media Streams send 8 kHz μ-law audio to your server over a WebSocket.
- **Why it mattered:** browser calls use WebRTC (SmallWebRTC); phone calls arrive over a Twilio WebSocket; provider STT/TTS APIs are WebSockets too. The same agent must handle both kinds of input (D-007).
- **Interview questions:**
  - Why is WebRTC preferred over WebSockets for audio from a user's device?
  - What is head-of-line blocking, and why does it matter for realtime audio?
  - What does a jitter buffer do, and what does it cost in latency?
- **References:** MDN WebRTC API docs · Twilio Media Streams docs · webrtcforthecurious.com

---

## System-design questions this project prepares you for

- Design a voice agent platform that handles 10,000 concurrent calls with P95 turn latency < 1 s.
- Design failover across STT providers so a provider outage causes no dead air.
- How would you evaluate a voice agent before shipping a prompt change? (regression evals in CI)
- How would you route between several ML providers using live quality and latency signals?
- How do you test a system whose inputs are realistic, messy human conversations? (synthetic callers, replay)
