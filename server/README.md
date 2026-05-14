# `server/` — Backend (REST + WebSocket + ASR runtime + note orchestrator)

Python 3.11 / FastAPI service that runs on the in-clinic GPU box. Receives audio over WebSocket from the Android client, performs streaming ASR, asks the LLM for a structured note, persists everything, and exposes REST endpoints for sessions and exports.

## Layout

```
server/
├── pyproject.toml            deps + tool config (ruff, pytest)
├── Dockerfile                CUDA base image
├── .env.example              env vars (HF_TOKEN, paths, ports)
└── src/medicscribe_server/
    ├── main.py               FastAPI app + lifespan + router wiring
    ├── config.py             pydantic-settings — loads project.properties + .env
    ├── api/                  REST routers
    │   ├── health.py
    │   ├── sessions.py       list / get / patch / delete sessions and notes
    │   └── exports.py        PDF / DOCX / JSON downloads
    ├── ws/                   WebSocket handlers
    │   ├── session.py        per-connection state machine
    │   └── protocol.py       pydantic message schemas (mirror Android Protocol.kt)
    ├── asr/                  ASR engine — adapter pattern
    │   ├── base.py           ASREngine ABC
    │   ├── faster_whisper.py default impl
    │   ├── vad.py            silero-vad
    │   └── registry.py       reads /llm/models/asr.yaml → instantiates engine
    ├── llm_client/           LLM transport (NOT prompts — those live in /llm)
    │   ├── base.py           LLMClient ABC
    │   ├── vllm.py
    │   ├── llamacpp.py
    │   └── registry.py       reads /llm/models/note_llm.yaml → instantiates client
    ├── notes/                note generation orchestrator
    │   ├── generator.py      load template from /llm/templates, call llm_client
    │   ├── schema_loader.py  JSON Schema → guided decoding params
    │   └── postprocess.py
    ├── store/                SQLite + filesystem
    │   ├── db.py             engine + session
    │   ├── models.py         SQLModel tables
    │   └── retention.py      purge audio after note generated (v1.0)
    └── util/
```

## Model swap workflow

1. Edit `/llm/models/asr.yaml` or `/llm/models/note_llm.yaml`.
2. Restart the server (or hit `POST /admin/reload-models` once that exists).
3. No code change.

The `registry.py` in each engine subpackage is the only place that maps yaml `engine` keys to concrete classes.

## Status

v1.0: `/health`, WS `/ws/scribe`, ASR via faster-whisper, single hardcoded SOAP_v1 template, exports as PDF/DOCX/JSON, audio purged immediately after note generated. No auth (LAN trust). No diarization.
