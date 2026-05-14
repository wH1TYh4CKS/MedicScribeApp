# MedicScribe

Medical transcription + structured-note tool for Malaysian clinics.

A doctor presses **Record** on an Android tablet during a consultation. Audio streams over the clinic LAN to a local GPU server which performs live multilingual ASR (English / Mandarin / Bahasa Melayu / Tamil — including code-switched Manglish) and generates a structured medical note with a 14B-class LLM. The note returns to the tablet for review, edit, and export. **No cloud egress.** PHI never leaves the clinic.

> **Status:** Phase 0 — scaffolding. No code yet. See [`PLAN.md`](./PLAN.md).

---

## Why this exists

Off-the-shelf medical scribes assume monolingual English consultations. Malaysian primary-care visits routinely mix four languages and Manglish slang inside a single sentence. We pair a large multilingual ASR (Whisper-large-v3) with a multilingual LLM (Qwen2.5-14B) on a single in-clinic GPU, so the doctor can speak naturally with the patient and still get a clean SOAP-style note in under 30 seconds.

## Architecture (one-liner)

`Android (Kotlin/Compose) ↔ WebSocket over LAN ↔ FastAPI server (faster-whisper streaming + silero-VAD + vLLM-served Qwen2.5-14B AWQ) on RTX 4090/3090.`

Full diagram + protocol in [`PLAN.md`](./PLAN.md). Component pins in [`VERSIONS.md`](./VERSIONS.md). Tunables in [`project.properties`](./project.properties).

## Repository layout

Three top-level code folders: **`app/`** (Android client), **`server/`** (backend), **`llm/`** (prompts + model registry + templates). Model swap = edit one yaml in `llm/models/`. Note-template authoring = edit one folder in `llm/templates/` — no server code touched.

```
MedicScribeApp/
├── README.md  CLAUDE.md  PLAN.md  VERSIONS.md  project.properties  .gitignore
│
├── app/                              Android client (UI/UX + client behaviour)
│   ├── README.md  build.gradle.kts  settings.gradle.kts  gradle/
│   └── tablet/                       Android Gradle module
│       └── src/main/
│           ├── AndroidManifest.xml
│           ├── kotlin/com/medicscribe/{ui/{theme,screens,components},audio,net,data,domain,export}/
│           └── res/
│
├── server/                           FastAPI + ASR runtime + note orchestrator
│   ├── README.md  pyproject.toml  Dockerfile  .env.example
│   └── src/medicscribe_server/
│       ├── main.py  config.py
│       ├── api/         REST routers (health, sessions, exports)
│       ├── ws/          WebSocket session + protocol
│       ├── asr/         engine adapters + registry (faster_whisper, vad)
│       ├── llm_client/  LLM transport adapters + registry (vllm, llamacpp)
│       ├── notes/       generator (loads from /llm/templates, calls llm_client)
│       ├── store/       SQLite + filesystem
│       └── util/
│
├── llm/                              Prompts, templates, model registry — content not code
│   ├── README.md
│   ├── models/                       ← model swap lives here
│   │   ├── asr.yaml
│   │   └── note_llm.yaml
│   ├── prompts/                      shared fragments
│   │   ├── system_doctor_scribe.jinja
│   │   ├── style_guides/{soap.md, manglish_rules.md}
│   │   └── few_shot/{soap_example_en.json, soap_example_manglish.json}
│   ├── templates/                    one folder per note template
│   │   └── soap_v1/{prompt.jinja, output_schema.json, meta.yaml}
│   ├── custom/                       doctor-authored templates (v1.1)
│   │   └── _example/                 contract reference
│   └── eval/                         multilingual eval (Phase 5)
│
├── data/                             runtime audio / transcripts / notes — gitignored
└── docs/                             ARCHITECTURE.md, PRIVACY_PDPA.md, PROMPT_TEMPLATES.md (TBD)
```

## Hard constraints (non-negotiable)

- Note generation latency ≤ **30 s** after Stop is pressed.
- All persistence is **server-side**; phone is a thin client.
- **LAN-only** — no cloud APIs that see audio or text.
- **Code-switched multilingual** ASR is the core feature, not optional.
- Doctor can pick or **customise the note template** server-side (Jinja).

## Hardware target

- **Server:** Linux box with RTX 4090 / 3090 (24 GB VRAM), 32 GB+ RAM, NVMe.
- **Client:** Android tablet, Android 8.0+ (`minSdk=26`), wired or Wi-Fi on same LAN.

## Prerequisites (will be needed once Phase 0 ships)

- Docker + docker compose v2
- NVIDIA driver ≥ 550, CUDA 12.4, `nvidia-container-toolkit`
- Android Studio Ladybug+ (AGP 8.7, JDK 17)
- HuggingFace token (only for diarization in v1.1)

## Run (TBD — Phase 0 not yet built)

```bash
# server
docker compose up        # placeholder

# android
./gradlew installDebug   # placeholder
```

Concrete commands land at end of Phase 0.

## Scope

**v1.0 (MVP for client demo):** Record → live transcript → single SOAP template → doctor edit → export PDF/DOCX/JSON. No auth, no diarization, no retention toggle, no custom templates. Audio purged after note generated.

**v1.1 (post-demo):** retention toggle, custom note templates + editor, "what to save" toggles, diarization, PIN auth, EMR connector (only on clinic request).

## Phase status (v1.0)

- [x] Phase 0a — Plan + memory + folder skeleton + properties + versions
- [ ] Phase 0b — `docker-compose.yml` + FastAPI `/health` + Android empty Compose app
- [ ] Phase 1 — End-to-end audio capture → server WAV
- [ ] Phase 2 — Live ASR (Whisper streaming + VAD)
- [ ] Phase 3 — Note generation (vLLM + SOAP_v1 prompt + JSON-schema decoding)
- [ ] Phase 4 — Doctor review / edit / export (PDF + DOCX + JSON)
- [ ] Phase 5 — Multilingual eval + tuning + audio purge → **v1.0 demo build**

## Phase status (v1.1)

- [ ] Phase 6 — retention toggle + template CRUD + custom editor + diarization + auth + EMR

## Compliance

Designed for Malaysian PDPA 2010. Audio default retention = 24 h then auto-purged; transcripts/notes retained per clinic policy. See [`docs/PRIVACY_PDPA.md`](./docs/PRIVACY_PDPA.md) (TBD).

## License

Proprietary — all rights reserved (until decided otherwise).
