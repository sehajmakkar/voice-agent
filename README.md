# Swar 🎙️

**A voice agent for Indian callers that uses the best speech model for each language, and switches between models mid-call without the caller noticing.**

Swar is a working voice agent (clinic appointment booking and EMI payment reminders) that you can talk to in the browser or over the phone. On top of the agent is a reliability layer. That layer is the real project.

---

## The problem

Voice agents in production rarely fail because the AI models are bad. They fail in the gaps *between* the models.

1. **They're slow.** Every step (speech-to-text, then the LLM, then text-to-speech) adds delay. After about 1.2 seconds of silence, callers start hanging up.
2. **No single model handles India.** Indian callers mix languages mid-sentence: Hindi + English, Tamil + English, Bengali + English. One provider is good at Hinglish, another at Tamil-English, and noisy phone audio makes all of them worse.
3. **Switching models is slow.** The obvious way to use the right model is to wait for the sentence to end, detect the language, connect to another provider and resend the audio. That adds 0.3–1 second, which is enough to make the call feel broken.
4. **Providers slow down or go down.** Most agents just wait, and the caller hears dead air.
5. **Turn-taking is clumsy.** Agents cut people off during a pause, or stop talking every time the caller says "haan".

## What Swar does

- **Detects the language mix early** (from about the first half-second of speech) and sends audio to the provider that handles it best.
- **Switches providers mid-call in under 50 ms**, without losing any words.
- **Watches each provider's speed live** and moves away from a slow one before the caller hears silence.
- **Knows when the caller has actually finished**, and doesn't treat "haan" or "hmm" as an interruption.
- **Keeps talking while it works.** It says something natural while a booking is being made.
- **Measures every turn**, so you can see exactly which step was slow.

The routing is based on data: a small benchmark of each provider on noisy, phone-quality Indian audio decides which provider gets which language mix.

## How switching stays fast

| Technique | What it does |
|---|---|
| **Early language detection** | Decides from the greeting, the caller's phone region and the first ~0.5 s of speech, not after the sentence ends |
| **Warm connections** | Keeps connections to likely providers open, so a switch skips 100–300 ms of connection setup |
| **Audio replay buffer** | Keeps the last few seconds of audio and replays it to the new provider, so no words are lost |
| **Speculative streaming** | When unsure, sends audio to two providers for a moment and keeps the better result |
| **Sticky routing** | Doesn't switch because of one English word; only switches when it's confident |
| **One voice per call** | Uses one multilingual voice, so the agent doesn't sound like a different person after a switch |

---

## How it's measured

Every number is compared against a **baseline**: the same agent using one provider, with no routing.

| Metric | Question it answers | Target |
|---|---|---|
| **Response time** | From the moment the caller stops speaking, how long until the agent starts speaking? (P50 / P95) | < 800 ms / < 1.2 s |
| **Switch cost** | How much time does a provider switch add, and are any words lost? | < 50 ms, 0 words lost |
| **Transcription accuracy** | How many words are wrong, per language mix, on phone audio? (WER / CER) | Better than the best single provider |
| **Failover** | When a provider fails mid-call, how fast does Swar recover, and how often is there more than 1.5 s of silence? | < 300 ms recovery, < 1% of turns |
| **Turn-taking** | How often does the agent cut the caller off, or stop for a "haan"? | < 5% of turns |
| **Task success** | Was the booking or reminder actually completed correctly? | > 90% of calls |
| **Cost** | What does one minute of a call cost, including the extra cost of switching? | Reported vs baseline |

**How the tests run**
- **Test calls:** about 50 per language mix (Hinglish, Tamil-English, Bengali-English), recorded or generated, then converted to noisy 8 kHz phone-quality audio.
- **AI callers:** LLM-driven callers phone the agent, switch languages, pause, interrupt and say "haan haan".
- **Chaos tests:** a provider is deliberately slowed down or cut off in the middle of a call.
- **One command:** `make eval` runs everything and writes a report (baseline vs Swar). CI runs it on every change to routing or turn detection.

---

## Architecture

```
Caller: browser (WebRTC) or phone (Twilio)
  │ audio in                                          ▲ audio out
  ▼                                                   │
Pipecat pipeline, served by FastAPI
  1. Silero VAD + turn detection + backchannel filter
  2. Swar router: language ID · provider health · failover
                  warm connections · audio replay buffer
       └─► STT adapters: Sarvam · Deepgram
  3. LLM + tools: Gemini (OpenAI as fallback) · booking tools · filler speech
  4. Swar router ─► TTS adapters: Sarvam Bulbul · Cartesia ──┘

Every turn ─► OpenTelemetry traces → Jaeger
          ─► turn metrics → Postgres → Grafana
Live call state ─► Redis
```

The router, the adapters and the replay buffer live in a plain-Python core that doesn't depend on Pipecat. Pipecat only connects them to the call.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | **Python 3.12 + asyncio** | Voice frameworks, provider SDKs and ML tools are all Python |
| Voice pipeline | **Pipecat** | Built from small processors, so adding our own router, buffer and turn logic is easy. Ships VAD, turn detection, telephony and tracing |
| Browser calls | **Pipecat SmallWebRTC** | Peer-to-peer WebRTC with no extra account, good for development |
| Phone calls | **Twilio** (Exotel for Indian numbers, if business KYC allows) | Quickest way to get a working phone number |
| Server | **FastAPI** | WebRTC signalling, Twilio webhooks, a small API |
| Speech-to-text | **Sarvam, Deepgram** (+ Smallest or Gnani if API access works out) | An Indian-language specialist vs a fast global model: the two ends the router chooses between |
| Text-to-speech | **Sarvam Bulbul, Cartesia** | Natural Indian voices vs very low latency |
| LLM | **Gemini Flash** (primary), **OpenAI mini model** (fallback) | Fast first token, cheap, handles Hinglish; a second provider allows failover |
| VAD / turn detection | **Silero VAD, Smart Turn** | Open source, runs on CPU, built into Pipecat |
| Language ID | Script and word-list checks on partial transcripts, plus an audio language-ID model | Model chosen by measurement in Phase 5 |
| Storage | **Postgres** (SQLAlchemy + Alembic), **Redis** | Calls, turns and bookings in Postgres; Redis for live call state once there's more than one worker |
| Observability | **OpenTelemetry, Jaeger, Grafana** | Per-turn waterfalls and latency dashboards without building a custom UI |
| Evals | **jiwer** (WER/CER), **pytest**, LLM judge, **GitHub Actions** | Accuracy scoring, tests, automated regression checks |
| Infra | **Docker Compose** on one VM in an India region | Close to Indian providers and callers; enough for the demo and load tests |
| Tooling | **uv, ruff, pre-commit** | Fast installs, one linter/formatter |

The reasons for each choice, and the alternatives considered, are in [decisions.md](decisions.md).

---

## Roadmap

| Phase | What gets built | Milestone |
|---|---|---|
| 0 | Setup, audio basics, Pipecat basics | |
| 1 | Basic agent: one STT, one LLM, one TTS, in the browser | |
| 2 | Per-turn tracing, baseline latency numbers | |
| 3 | Provider adapters behind one interface | |
| 4 | Benchmark of Indian speech-to-text on phone audio | **v0: first public results** |
| 5 | Router: language routing, health scores, failover | |
| 6 | Fast switching: warm connections, replay buffer, speculative streaming | **v1: core result** |
| 7 | Eval harness: AI callers, LLM judge, `make eval`, CI | |
| 8 | Turn-taking: semantic end-of-turn, backchannel filter | |
| 9 | Booking tools, filler speech | |
| 10 | Real phone number | |
| 11 | Load test, cost per minute, deployment | |
| 12 | Demo video and write-up | **v2: complete** |

Task-level detail is in [plan.md](plan.md).

## What I'll learn

**AI / voice:** streaming STT → LLM → TTS pipelines · VAD vs turn detection · handling interruptions · code-switching and language ID · tool calls under time pressure · evaluating voice agents (WER/CER, LLM judges, regression evals)

**Backend:** realtime audio over WebRTC and WebSockets · asyncio concurrency and cancellation · latency engineering (P95/P99, budgets) · circuit breakers, hedged requests and failover · connection pooling and buffering · tracing with OpenTelemetry · telephony · load and chaos testing

Notes and interview questions are in [learnings.md](learnings.md). Problems hit along the way are in [challenges.md](challenges.md).

---

## Target companies

**Indian voice AI**: Swar's benchmark, Indian-language routing and real tasks
1. **Sarvam AI**: Samvaad agents, Saaras speech-to-text, Bulbul text-to-speech
2. **Bolna (YC F25)**: voice agent orchestration across Indian languages
3. **Smallest.ai**: voice models and agents
4. **Gnani.ai**: full in-house voice stack
5. **Ringg AI**: multichannel voice agents
6. **Skit.ai**: contact-centre voice agents
7. **GreyLabs AI**: voice AI for banks and lenders
8. **Edesy**: self-serve voice agent builder
9. **Exotel**: telephony and realtime voice APIs

**Testing and monitoring**: Swar's eval harness, AI callers and chaos tests

10. **Hamming AI (YC S24)**: automated voice agent testing
11. **Cekura (YC F24)**: testing and monitoring for voice and chat agents
12. **Roark (YC W25)**: replays real calls against updated agents
13. **Coval**: simulation-first voice agent testing
14. **Bluejay (YC S25)**: QA for voice and text agents
15. **Future AGI**: voice agent evaluation and observability

**Platforms and infrastructure**: Swar's latency, failover and turn-taking work

16. **Vapi**: managed voice agent platform
17. **Retell AI (YC W24)**: phone agents
18. **LiveKit**: open-source realtime voice/video and Agents framework
19. **Pipecat / Daily**: open-source Python voice pipelines
20. **Deepgram**: speech-to-text and voice agent APIs
21. **Cartesia**: low-latency text-to-speech
22. **ElevenLabs**: voices and agents

**New YC companies**
23. **Callab AI (YC X26)**: voice agents for any phone system
24. **KugelAudio (YC X26)**: on-prem multilingual voice model
25. **Wavelength**: voice-first AI companion

---

## Author

**Sehaj Preet** · [sehaj.tech](https://sehaj.tech) · [GitHub](https://github.com/sehajmakkar) · [LinkedIn](https://linkedin.com/in/sehajmakkar) · [X](https://x.com/kryptokodes)
