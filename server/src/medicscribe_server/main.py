from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from medicscribe_server.api import health
from medicscribe_server.config import settings
from medicscribe_server.ws import router as ws_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.asr_engine = None
    app.state.make_endpointer = None
    if settings.asr_enabled:
        from medicscribe_server.asr.registry import build_asr, build_endpointer

        logger.info("Loading ASR model from %s ...", settings.asr_config_path)
        app.state.asr_engine = build_asr(settings.asr_config_path)
        app.state.make_endpointer = lambda: build_endpointer(settings.asr_config_path)
        logger.info("ASR model ready")
    else:
        logger.info("ASR disabled (MEDICSCRIBE_ASR_ENABLED=false) — WAV-only mode")
    try:
        yield
    finally:
        if app.state.asr_engine is not None:
            app.state.asr_engine.close()


def create_app() -> FastAPI:
    app = FastAPI(title="MedicScribe", version="0.0.1", lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(ws_router.router)
    return app


app = create_app()
