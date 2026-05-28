from fastapi import APIRouter, WebSocket

from medicscribe_server.config import settings
from medicscribe_server.ws.session import WSSession

router = APIRouter()


@router.websocket("/ws/scribe")
async def scribe_ws(ws: WebSocket) -> None:
    await ws.accept()
    asr = getattr(ws.app.state, "asr_engine", None)
    make_endpointer = getattr(ws.app.state, "make_endpointer", None)
    note_generator = getattr(ws.app.state, "note_generator", None)
    session = WSSession(
        ws=ws,
        audio_dir=settings.audio_dir,
        sample_rate=settings.audio_sample_rate,
        asr=asr,
        endpointer=make_endpointer() if (asr and make_endpointer) else None,
        note_generator=note_generator,
    )
    await session.run()
