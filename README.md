# MedicScribe

**A medical scribe that speaks Manglish, and keeps nothing.** A doctor presses Record
during a consultation; audio streams to a GPU server on the clinic's own network; a
structured SOAP note comes back in under 30 seconds. No cloud. No database. The audio
is deleted before the note is even generated.

---

## The problem

Off-the-shelf medical scribes assume a monolingual English consultation. A Malaysian
primary-care visit does not work that way — English, Mandarin, Bahasa Melayu, Tamil and
Manglish slang routinely appear inside a *single sentence*:

> "Your sugar level, uh, *sudah naik* — so we need to, ah, adjust the metformin lah."

The second problem is regulatory, and it is the harder one. Malaysian clinics operate
under the PDPA 2010. A scribe that uploads consultation audio to someone else's cloud
makes the clinic responsible for a data flow it cannot inspect. That is what killed
every off-the-shelf option for the clinics I spoke to — not accuracy.

## What it does

- **Records** from an Android tablet (Kotlin/Compose) or a browser page.
- **Transcribes** with Whisper large-v3 in a single `task: translate` pass, so any
  input language comes out as an English note.
- **Generates** a SOAP note with a 27B-class model, streamed back for the doctor to
  read, edit, and copy into the clinic's own record system.
- **Forgets.** Audio is unlinked at Stop, the transcript lives in RAM, the note is
  never written to disk. `GET /transparency` reports this live.

MedicScribe is an assistant, not a record system. The clinic's existing records stay
the system of record.

## Decisions worth defending

**Translate at ASR, not after.** The obvious design routes by language: detect, pick a
model, transcribe, then translate. I collapsed that into one Whisper pass with
`task: translate`. No language picker, no model routing, no second hop — and because
the product's output is an English note, nothing is lost. A Malaysian Whisper
fine-tune was tested for this and **rejected**: under `translate` it leaves Malay
untranslated and cannot emit Mandarin Hanzi. The reasoning is kept in
[`llm/models/asr.yaml`](llm/models/asr.yaml) next to the setting it justifies.

**Measured failure modes, not just features.** Two that shaped the build:

- *Whisper is confidently wrong about language.* On a real 22-minute Mandarin
  dermatology consult it picked Malay at p=0.62 and emitted Malay prose for the entire
  file — silently, no error. Raising `language_detection_segments` to 8 with a 0.7
  threshold fixed the low-confidence cases (zh detection 0.55 → 0.91) but **not** the
  confident-wrong one: Malaysian-accented English still reads as Malay at p=0.91. More
  scanning just finds a more confident wrong window. `task: translate` degrades this
  to "slightly worse English" rather than destroying the note — which is exactly why
  `transcribe` was not an option.
- *Greedy decoding degenerates on long noisy transcripts.* A 22-minute code-switched
  consult looped one bullet forever and never reached O:/A:/P:. `repetition_penalty:
  1.05` — low enough not to distort a dosage — fixed it.

**Privacy enforced in code, not in a policy PDF.** No database, no ORM, no audio
archive. A TTL reaper sweeps stray files on boot and on an interval so a crash-orphaned
WAV cannot survive a long uptime. `GET /transparency` returns the live audio file
count and whether the store is tmpfs, so the claim is checkable from outside.
Full data-lifecycle statement: [`docs/PRIVACY_PDPA.md`](docs/PRIVACY_PDPA.md).

**Prompt-level PHI defence.** The note prompt instructs the model to replace names, IC
numbers, phone numbers and addresses with `[REDACTED]` wherever they surface in the
transcript ([`llm/templates/sum_v1/prompt.jinja`](llm/templates/sum_v1/prompt.jinja)).

## Architecture

```
Android tablet  ─┐
                 ├─ WebSocket /ws/scribe ─→  FastAPI server  ─→  Whisper (ASR)
Browser page    ─┘        (int16 PCM)             │                    │
                                                  │              transcript (RAM)
                                                  │                    ▼
                          note ←── stream ────────┴──────  note LLM (OpenAI-compatible)
```

WebSocket protocol — client sends `start`, PCM frames, `stop`; server answers `ack`,
`transcript_partial`, `transcript_final`, **`audio_deleted`**, `note_progress`,
`note_done`, with `BUSY` / `IP_LIMIT` rejections under load.

HTTP surface, complete:

| | |
|---|---|
| `GET /` · `/scribe` | the browser recording page |
| `GET /feedback` | product feedback form (never clinical content) |
| `GET /health` | liveness |
| `GET /health/ready` | `{ready, asr, note_llm}`, 503 until both load |
| `GET /transparency` | live privacy receipt |
| `POST /api/feedback` | appends JSONL |
| `WS /ws/scribe` | the recording session |

## Run it

**Container** — CPU ASR, bring your own note model. Ships no weights.

```bash
MEDICSCRIBE_NOTE_ENDPOINT=http://host.docker.internal:8000/v1 \
docker compose up --build
# then open http://localhost:8080
```

`GET /health/ready` stays 503 with `note_llm: false` until that endpoint answers —
that is the intended behaviour, not a bug. Any OpenAI-compatible server works (vLLM,
llama.cpp, Ollama). Container ASR uses Whisper `small` on CPU because large-v3 on CPU
is unusably slow; production uses large-v3 on CUDA.

**Full local GPU stack** — what this was actually built and field-tested on: 4× RTX
3090, Whisper large-v3 on CUDA, vLLM serving Qwen3.8-27B at TP=4.

```bash
./scripts/start-all.sh      # starts vLLM, waits for it, then the server
./scripts/stop-all.sh
```

This path expects a specific machine. Model paths and launch knobs live in
[`llm/models/note_llm.yaml`](llm/models/note_llm.yaml); every one is overridable via
`MEDICSCRIBE_NOTE_ENDPOINT` / `_MODEL` / `_API_KEY`.

**Android client**

```bash
./gradlew :tablet:assembleDebug     # set medicscribe.serverHost in app/gradle.properties
```

## Layout

| Path | |
|---|---|
| `server/` | FastAPI backend — ASR, note orchestration, WebSocket, static web client |
| `server/src/medicscribe_server/web/` | the browser client (vanilla JS + AudioWorklet) |
| `app/tablet/` | Android client (Kotlin, Compose Material 3) |
| `llm/models/` | ASR + note-LLM registry yaml — swap models without touching code |
| `llm/templates/`, `llm/prompts/` | Jinja note templates and few-shot examples (synthetic) |
| `scripts/` | stack start/stop, audio prep, model bake-off harnesses |
| `docs/PRIVACY_PDPA.md` | the data-lifecycle statement clinics were asked to sign |

## Tests

```bash
cd server && pip install -e '.[dev]' && pytest -m "not slow"
```

47 tests, plus 2 marked `slow` that download real ASR weights.

## Status and limits

Built and field-tested on real consultations; a clinic pitch was **declined on legal
and ethics grounds**, and capture-without-disk is the gate before re-pitching. So:
this works, and it is not deployed.

- **Not a medical device.** Not certified, not approved, not fit for clinical use.
- One language is locked per consultation — Whisper decides once and holds.
- No Android test suite.
- No screenshots in this repo: the originals showed a real consultation and were
  removed rather than published.

## License

**All rights reserved.** See [`LICENSE`](LICENSE). Published for reading, not for use.
