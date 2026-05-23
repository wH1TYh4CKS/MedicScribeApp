from fastapi import APIRouter, WebSocket

from medicscribe_server.config import settings
from medicscribe_server.ws.session import WSSession

router = APIRouter()


@router.websocket("/ws/scribe")
async def scribe_ws(ws: WebSocket) -> None:
    await ws.accept()
    session = WSSession(
        ws=ws,
        audio_dir=settings.audio_dir,
        sample_rate=settings.audio_sample_rate,
    )
    await session.run()
