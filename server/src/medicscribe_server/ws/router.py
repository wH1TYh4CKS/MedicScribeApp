from fastapi import APIRouter, WebSocket

from medicscribe_server.config import settings
from medicscribe_server.ws.session import WSSession

router = APIRouter()


@router.websocket("/ws/scribe")
async def scribe_ws(ws: WebSocket) -> None:
    await ws.accept()
    asr = getattr(ws.app.state, "asr_engine", None)
    note_generator = getattr(ws.app.state, "note_generator", None)
    # Process-wide locks so concurrent sessions don't call the shared (non-reentrant)
    # WhisperModel / note LLM at the same time. Created once in the app lifespan.
    asr_lock = getattr(ws.app.state, "asr_lock", None)
    note_lock = getattr(ws.app.state, "note_lock", None)
    # Batch-at-Stop transcription uses whisper's own VAD (asr.yaml vad_filter);
    # the old per-connection silero endpointer is gone (see WSSession._on_stop).
    session = WSSession(
        ws=ws,
        audio_dir=settings.audio_dir,
        sample_rate=settings.audio_sample_rate,
        asr=asr,
        note_generator=note_generator,
        asr_lock=asr_lock,
        note_lock=note_lock,
    )
    await session.run()
