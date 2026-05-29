from fastapi import APIRouter, WebSocket

from medicscribe_server.config import settings
from medicscribe_server.ws.session import WSSession

router = APIRouter()


@router.websocket("/ws/scribe")
async def scribe_ws(ws: WebSocket) -> None:
    await ws.accept()
    asr = getattr(ws.app.state, "asr_engine", None)
    note_generator = getattr(ws.app.state, "note_generator", None)
    # Batch-at-Stop transcription uses whisper's own VAD (asr.yaml vad_filter);
    # the old per-connection silero endpointer is gone (see WSSession._on_stop).
    session = WSSession(
        ws=ws,
        audio_dir=settings.audio_dir,
        sample_rate=settings.audio_sample_rate,
        asr=asr,
        note_generator=note_generator,
    )
    await session.run()
