# `server/` — FastAPI backend

Receives audio over a WebSocket, transcribes it, asks a note LLM for a structured
SOAP note, streams the note back, and **stores nothing**. There is no database and
no ORM: the audio file is unlinked at Stop and the transcript lives in RAM for the
few seconds note generation takes.

## Layout

```
server/
├── pyproject.toml              deps + ruff/pytest config
├── Dockerfile                  python:3.12-slim — app only, no CUDA
├── .env.example                MEDICSCRIBE_* settings
└── src/medicscribe_server/
    ├── main.py                 create_app() — lifespan, router wiring, static mount
    ├── config.py               pydantic-settings, env prefix MEDICSCRIBE_
    ├── api/
    │   ├── health.py           /health, /health/ready, /transparency
    │   ├── feedback.py         POST /api/feedback (JSONL append, never clinical text)
    │   └── web.py              serves the browser client
    ├── ws/
    │   ├── router.py           WS /ws/scribe
    │   ├── session.py          per-connection state machine + concurrency caps
    │   └── protocol.py         message schemas (mirror Android Protocol.kt)
    ├── asr/
    │   ├── base.py             ASREngine ABC
    │   ├── faster_whisper_engine.py
    │   └── registry.py         reads llm/models/asr*.yaml → instantiates engine
    ├── llm_client/
    │   ├── base.py             LLMClient ABC
    │   ├── openai_compat.py    any OpenAI-compatible endpoint
    │   ├── stub.py             fixed response, for tests
    │   └── registry.py         reads llm/models/note_llm*.yaml; env overrides win
    ├── notes/
    │   ├── template.py         loads Jinja templates from llm/templates/
    │   └── generator.py        renders the prompt, calls the client, retries
    ├── store/
    │   ├── audio_writer.py     WAV writer for the in-flight recording
    │   └── reaper.py           TTL sweep — boot + interval, kills crash orphans
    └── web/                    browser client: HTML, AudioWorklet, self-hosted fonts
```

VAD lives inside the ASR engine (`vad_filter`), not as a separate module.

## Model swap workflow

1. Edit `llm/models/asr.yaml` or `llm/models/note_llm.yaml`, or point the
   `MEDICSCRIBE_*_CONFIG_PATH` settings at a different file.
2. Restart the server.
3. No code change.

Each `registry.py` is the only place mapping a yaml `engine` key to a concrete class.

**Environment beats yaml.** `MEDICSCRIBE_NOTE_ENDPOINT`, `_MODEL`, `_API_KEY` and
`_ENGINE` override the committed config, so the tracked yaml can record the tuned GPU
deployment while a container or CI points somewhere else. Secrets never go in yaml.

## Running

```bash
pip install -e '.[dev]'
uvicorn medicscribe_server.main:app --host 0.0.0.0 --port 8080
pytest -m "not slow"          # 47 tests; 2 slow ones download real ASR weights
```

Tests read prompt templates from `../llm`, so run them from a full checkout.

## Status

No auth — this was designed for a trusted clinic LAN, with a Cloudflare tunnel used
only for a supervised public trial. Concurrency is capped globally and per IP
(`max_concurrent_sessions`, `max_sessions_per_ip`) and a recording is hard-capped at
30 minutes, all as disk-DoS guards. No diarization. No export formats beyond copying
the note text.
