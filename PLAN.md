# MedicScribe — Implementation Plan

> Mirror of approved plan at `~/.claude/plans/witty-chasing-sparkle.md`.
> If the two diverge, the file under `~/.claude/plans/` is authoritative until you reconcile.

## Context

Greenfield medical transcription tool for Malaysian clinics. Doctor presses Record on an Android tablet during a consultation; audio streams to a local LAN server (RTX 4090/3090, 24 GB VRAM) which runs live ASR + medical-note generation; the structured note is pushed back to the Android app for the doctor to review, edit, export, and save.

Why this design:
- Malaysian patients code-switch mid-sentence (English / Mandarin / Bahasa Melayu / Tamil + Manglish slang). Only large multilingual ASR models (Whisper-large-v3) handle this reliably — too heavy for a phone.
- Server-side ASR keeps the phone light, lets us upgrade models without app updates, and gives the same GPU that runs the note LLM access to clean transcript chunks.
- LAN-only server keeps PHI inside the clinic (PDPA 2010 friendly). No cloud dependency.
- Customisable note templates because each doctor / specialty wants different structure (SOAP vs symptom-only vs vendor-specific).

Hard constraints:
- Note generation ≤ 30 s after Stop is pressed.
- Live transcript visible during recording.
- All data stored server-side; phone is a thin client.
- Doctor reviews + edits + exports the final note from the app.

---

## Architecture

```
┌─────────────────────────┐         WebSocket (LAN)        ┌──────────────────────────────────┐
│  Android Tablet (Kotlin)│ ──── PCM 16 kHz mono ─────────▶│  Local Server (FastAPI + Python) │
│  ┌───────────────────┐  │                                │                                  │
│  │ Record / Stop UI  │  │ ◀─── live transcript chunks ───│  ┌────────────────────────────┐  │
│  │ Live transcript   │  │                                │  │ Whisper-large-v3 (faster-  │  │
│  │ Note review/edit  │  │ ◀─── final note JSON ──────────│  │ whisper, CUDA, streaming)  │  │
│  │ Export PDF/DOCX   │  │                                │  └────────────┬───────────────┘  │
│  └───────────────────┘  │                                │               │ chunks            │
└─────────────────────────┘                                │               ▼                   │
                                                           │  ┌────────────────────────────┐  │
                                                           │  │ Qwen2.5-14B-Instruct (Q4,  │  │
                                                           │  │ vLLM or llama.cpp). Note   │  │
                                                           │  │ generator + template engine│  │
                                                           │  └────────────┬───────────────┘  │
                                                           │               ▼                   │
                                                           │  ┌────────────────────────────┐  │
                                                           │  │ SQLite + filesystem store  │  │
                                                           │  │ (sessions, transcripts,    │  │
                                                           │  │  notes, audio retention)   │  │
                                                           │  └────────────────────────────┘  │
                                                           └──────────────────────────────────┘
```

VRAM budget on RTX 4090 (24 GB):
- faster-whisper large-v3 fp16 ≈ 6 GB
- Qwen2.5-14B-Instruct AWQ/Q4 ≈ 10–11 GB
- KV cache + diarization model ≈ 4–6 GB
- Headroom ≈ 1–2 GB ✅

---

## Tech Stack

### Android client
- **Language**: Kotlin + Jetpack Compose
- **Audio**: `AudioRecord` API, 16 kHz mono PCM, 20 ms frames
- **Transport**: OkHttp WebSocket — binary frames (audio out), JSON frames (transcript / note in)
- **Permissions**: `RECORD_AUDIO`, `INTERNET`, `ACCESS_NETWORK_STATE`
- **State**: ViewModel + Kotlin Flows for live transcript stream
- **Note editor**: Compose `BasicTextField` with markdown render
- **Export**: PDF via Android `PrintAttributes`, DOCX via Apache POI (`poi-ooxml` slim build)

### Server
- **Runtime**: Python 3.11, FastAPI + Uvicorn (ASGI), single process per GPU
- **ASR**: `faster-whisper` large-v3 (CTranslate2 backend, fp16 on CUDA)
  - Streaming: 5 s rolling window, 1 s hop, VAD-gated
  - Language detect = `multilingual`, no forced language → handles code-switch
- **VAD**: `silero-vad` (tiny, CPU) before sending to Whisper to cut silence
- **Diarization** (v1.1): `pyannote/speaker-diarization-3.1` — Doctor / Patient labels
- **Note LLM**: Qwen2.5-14B-Instruct AWQ via **vLLM** (best throughput) or llama.cpp server
  - Why Qwen2.5: strong CN/EN, decent BM/TA, 32k context, Apache 2.0
  - Fallback: SeaLLM-v3-7B if BM/TA quality insufficient
- **Templates**: Jinja2 prompt templates in `server/app/notes/templates/*.jinja` — doctor picks via dropdown, can author custom in admin UI (v1.1)
- **Storage**: SQLite (sessions, notes, templates) + `data/audio/` (24 h retention, configurable) + `data/transcripts/`
- **Config**: `pydantic-settings`, `.env` driven

### Protocol (WebSocket)
Client → server (binary): raw 16-bit PCM frames, 20 ms each.
Client → server (JSON control):
```json
{"type":"start","session_id":"uuid","template":"soap_v1","languages":["en","zh","ms","ta"]}
{"type":"stop"}
```
Server → client (JSON):
```json
{"type":"transcript_partial","text":"...","speaker":"doctor","t":12.4}
{"type":"transcript_final","text":"...","speaker":"patient","t":15.1}
{"type":"note_progress","stage":"generating","pct":40}
{"type":"note_done","note":{...},"raw_transcript":"..."}
```

---

## Repo layout

Three code folders: `app/` (Android), `server/` (backend), `llm/` (prompts + templates + model registry — content not code).

```
MedicScribeApp/
├── README.md  CLAUDE.md  PLAN.md  VERSIONS.md  project.properties  .gitignore
│
├── app/                              Android client (UI/UX + client behaviour)
│   ├── build.gradle.kts  settings.gradle.kts  gradle.properties  gradle/
│   └── tablet/                       Android Gradle module
│       ├── build.gradle.kts
│       └── src/main/
│           ├── AndroidManifest.xml
│           ├── kotlin/com/medicscribe/
│           │   ├── MainActivity.kt
│           │   ├── ui/{theme,screens,components}/
│           │   ├── audio/   AudioCapture, PcmStreamer
│           │   ├── net/     WsClient, RestClient, Protocol
│           │   ├── data/    SessionRepo, SettingsStore
│           │   ├── domain/  state models
│           │   └── export/  PdfExporter, DocxExporter, JsonExporter
│           └── res/
│
├── server/                           FastAPI + ASR + LLM client + note orchestrator
│   ├── pyproject.toml  Dockerfile  .env.example
│   ├── src/medicscribe_server/
│   │   ├── main.py  config.py
│   │   ├── api/         {health.py, sessions.py, exports.py}
│   │   ├── ws/          {session.py, protocol.py}
│   │   ├── asr/         {base.py, faster_whisper.py, vad.py, registry.py}
│   │   ├── llm_client/  {base.py, vllm.py, llamacpp.py, registry.py}
│   │   ├── notes/       {generator.py, schema_loader.py, postprocess.py}
│   │   ├── store/       {db.py, models.py, retention.py}
│   │   └── util/
│   └── tests/{conftest.py, test_health.py, test_asr.py, test_notes.py, fixtures/}
│
├── llm/                              Prompts + model registry + templates
│   ├── README.md
│   ├── models/                       ← model swap = edit yaml + restart
│   │   ├── asr.yaml                  faster-whisper / large-v3 / cuda
│   │   └── note_llm.yaml             vllm / Qwen2.5-14B-AWQ
│   ├── prompts/
│   │   ├── system_doctor_scribe.jinja
│   │   ├── style_guides/{soap.md, manglish_rules.md}
│   │   └── few_shot/{soap_example_en.json, soap_example_manglish.json}
│   ├── templates/
│   │   └── soap_v1/{prompt.jinja, output_schema.json, meta.yaml}
│   ├── custom/                       v1.1 — doctor-authored templates
│   │   └── _example/                 contract reference
│   └── eval/                         {manglish_corpus/, note_quality_rubric.md}
│
├── data/                             runtime audio/transcripts/notes — gitignored
└── docs/                             ARCHITECTURE.md, PRIVACY_PDPA.md, PROMPT_TEMPLATES.md
```

### Why this layout

- `llm/` is **content, not code** — prompt engineers and doctors author here without touching `server/`.
- Each note template = one folder containing `prompt.jinja` + `output_schema.json` + `meta.yaml`. Schema lives next to prompt; version pin lives next to schema.
- `server/asr/` and `server/llm_client/` use adapter + registry pattern. `llm/models/*.yaml` declares which engine + model is loaded. Model swap = edit one yaml line, restart.
- `server/llm_client/` (transport) is distinct from `llm/` (prompts). Naming makes the split explicit.
- `app/tablet/` (Gradle module) inside `app/` (Gradle root) keeps "1 folder for app" while leaving room for future `app/wear/` or `app/desktop/` modules.

---

## Implementation phases

### Phase 0 — Scaffolding (½ day)
- Init repo, write `CLAUDE.md` + project memory file. ✅ (this commit)
- `docker-compose.yml`: server + vLLM (Qwen2.5-14B-AWQ).
- Empty FastAPI app with `/health`.

### Phase 1 — Audio pipeline E2E, no LLM (1–2 days)
- Android `RecordScreen` with Record/Stop, mic permission.
- `AudioCapture` → `PcmStreamer` → WebSocket binary frames.
- Server WS endpoint receives PCM → dumps wav.
- Goal: 30 s of tablet audio appears intact on server.

### Phase 2 — Live ASR (2–3 days)
- `faster-whisper` streaming + silero-VAD on server.
- Emit `transcript_partial` / `transcript_final`.
- Android renders live transcript with auto-scroll.
- Manglish WER measurement on a small handcrafted corpus.

### Phase 3 — Note generation (2–3 days)
- vLLM serving Qwen2.5-14B-AWQ.
- `notes/generator.py` builds prompt from full transcript + chosen template.
- JSON-schema-constrained output via vLLM guided decoding.
- Stream `note_progress` then `note_done`.
- Latency budget: 2k tok prompt + 500 tok output @ 60 tok/s ≈ 8 s + ASR finalisation 5 s ≈ 13 s. ≤ 30 s ✅.

### Phase 4 — Review / edit / export (1–2 days)
- `ReviewScreen` with editable note sections.
- Save edits via REST `PATCH /sessions/{id}/note`.
- Export PDF (template-driven), DOCX, copy-to-clipboard.

### Phase 5 — v1.0 polish + multilingual eval (open) — END OF v1.0
- 50-conversation Manglish eval set, WER + manual note-quality scoring.
- Fall back to SeaLLM-v3 if Qwen note quality on BM/TA is poor.
- Quantisation tuning if VRAM tight.
- Audio purge-on-success wired in (no toggle yet).
- **Demo build cut here.**

### Phase 6 — v1.1 (post-demo)
- Template CRUD REST + Android dropdown picker before recording.
- Custom template editor (admin web UI).
- "What to save" toggle: audio / transcript / note independently.
- Audio retention toggle (24 h auto-purge vs keep).
- pyannote diarization → doctor/patient labels in transcript + note.
- Optional PIN auth per doctor.
- EMR connector (only if a clinic asks).

---

## Critical files (single source of truth)

- `server/src/medicscribe_server/asr/base.py` + `registry.py` — ASR adapter contract; downstream depends on the engine event shape, not on a specific impl.
- `server/src/medicscribe_server/llm_client/base.py` + `registry.py` — LLM transport contract.
- `llm/models/asr.yaml` and `llm/models/note_llm.yaml` — the only place model identity is declared.
- `server/src/medicscribe_server/notes/generator.py` — loads `llm/templates/<slug>/`, renders prompt, calls LLM client, validates against `output_schema.json`.
- `server/src/medicscribe_server/ws/protocol.py` — pydantic message schemas; Android `app/tablet/.../net/Protocol.kt` must mirror exactly.
- `app/tablet/.../audio/PcmStreamer.kt` — frame size + sample rate must match `server/src/medicscribe_server/ws/session.py`.
- `llm/templates/soap_v1/{prompt.jinja, output_schema.json}` — v1.0 note contract.

---

## Verification

E2E smoke test (after Phase 4):
1. `docker compose up` on the GPU box.
2. Install debug APK on Android tablet on same Wi-Fi.
3. Set server IP in app settings; tap Record.
4. Play a 60 s Manglish consultation recording into tablet mic.
5. Tap Stop. Expect:
   - Live transcript appeared during playback (≤ 3 s lag for partials).
   - Note JSON arrives ≤ 30 s after Stop.
   - Note contains: chief complaint, HPI, meds, allergies, plan.
   - Edit one field → Export PDF → PDF opens with edited content.
6. `sqlite3 data/scribe.db 'select * from sessions'` → one session, status `completed`.

Unit tests:
- `pytest server/tests` — ASR returns text within tolerance on `manglish_sample.wav`; note generator returns valid schema.
- `./gradlew test` — Protocol serialization round-trip; AudioCapture starts/stops cleanly.

Performance acceptance:
- Live partial latency: p50 ≤ 1.5 s, p95 ≤ 3 s.
- Final transcript flushed ≤ 5 s after Stop.
- Note returned ≤ 30 s after Stop on the GPU box.

---

## Scope split — v1.0 (MVP demo) vs v1.1

**v1.0 — fastest path to client demo. Ship this first.**
- Record / Stop UI on Android. No auth — phone joins LAN → app talks to server. No PIN, no login.
- Live transcript stream from server.
- Single hardcoded note template (SOAP_v1) on server. No template picker, no custom templates.
- Doctor edit screen → Save → Export PDF / DOCX / JSON (no EMR connector).
- Audio always deleted immediately after note generated. No retention toggle.
- No diarization (transcript appears as flat text).
- No multi-user / no profiles.

**v1.1 — post-demo, value adds.**
- Audio retention toggle (per session): keep audio vs auto-purge after 24 h.
- Customisable note structure — doctor picks fields to include / template to apply, with a custom template editor in admin UI.
- "What to save" toggle (audio yes/no, transcript yes/no, note yes/no).
- pyannote diarization (Doctor / Patient labels).
- Optional PIN auth per doctor.
- EMR connector (HL7/FHIR or vendor-specific) — only if a clinic asks.

## Carry-overs (not yet decided)

- `git init` deferred — initialise when v1.0 code starts landing.
