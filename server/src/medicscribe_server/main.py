from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from medicscribe_server.api import feedback, health, web
from medicscribe_server.config import settings
from medicscribe_server.ws import router as ws_router

logger = logging.getLogger(__name__)

# Surface medicscribe_server.* logs (session lifecycle + PDPA purge audit trail).
# Without an explicit handler the app logger is silent (root has none under
# uvicorn) and the "Session ... purged" audit line never appears.
_app_logger = logging.getLogger("medicscribe_server")
if not _app_logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(levelname)s:    [%(name)s] %(message)s"))
    _app_logger.addHandler(_h)
    _app_logger.setLevel(logging.INFO)
    _app_logger.propagate = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    from medicscribe_server.store.reaper import purge_recordings

    purge_recordings(settings.audio_dir, settings.recording_ttl_seconds)

    # Periodic sweep so a crash-orphan WAV (server killed mid-session) can't linger
    # for the box's whole uptime. Runs off the same TTL as the startup purge.
    async def _reaper_loop() -> None:
        while True:
            await asyncio.sleep(settings.reaper_interval_seconds)
            purge_recordings(settings.audio_dir, settings.recording_ttl_seconds)

    reaper_task = (
        asyncio.create_task(_reaper_loop()) if settings.reaper_interval_seconds else None
    )

    # Shared across all WS sessions — the ASR engine and note LLM below are single
    # instances and must not be entered concurrently. Bound to this event loop here.
    app.state.asr_lock = asyncio.Lock()
    app.state.note_lock = asyncio.Lock()

    app.state.asr_engine = None
    if settings.asr_enabled:
        from medicscribe_server.asr.registry import build_asr

        logger.info("Loading ASR model from %s ...", settings.asr_config_path)
        app.state.asr_engine = build_asr(settings.asr_config_path)
        logger.info("ASR model ready")
    else:
        logger.info("ASR disabled (MEDICSCRIBE_ASR_ENABLED=false) — WAV-only mode")

    app.state.note_generator = None
    if settings.note_enabled:
        from medicscribe_server.llm_client.registry import build_llm_client
        from medicscribe_server.notes.generator import NoteGenerator
        from medicscribe_server.notes.template import NoteTemplate

        client = build_llm_client(settings.note_config_path)
        template = NoteTemplate.load(settings.note_template, settings.llm_root)
        app.state.note_generator = NoteGenerator(client, template)
        logger.info("Note generator ready (engine from %s)", settings.note_config_path)
    else:
        logger.info("Note generation disabled (MEDICSCRIBE_NOTE_ENABLED=false)")

    try:
        yield
    finally:
        if reaper_task is not None:
            reaper_task.cancel()
        if app.state.asr_engine is not None:
            app.state.asr_engine.close()
        if app.state.note_generator is not None:
            app.state.note_generator.close()


def create_app() -> FastAPI:
    app = FastAPI(title="MedicScribe", version="0.0.1", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(ws_router.router)
    app.include_router(web.router)
    app.include_router(feedback.router)
    app.mount(
        "/static/scribe",
        StaticFiles(directory=web.WEB_DIR),
        name="scribe-static",
    )
    return app


app = create_app()
