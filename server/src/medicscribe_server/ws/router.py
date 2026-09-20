from fastapi import APIRouter, WebSocket

from medicscribe_server.config import settings
from medicscribe_server.ws.protocol import ErrorMessage
from medicscribe_server.ws.session import WSSession

router = APIRouter()


def _client_ip(ws: WebSocket) -> str:
    """Visitor IP for per-IP limits. Behind the Cloudflare tunnel every socket
    arrives from localhost, so the real address only exists in the tunnel's
    CF-Connecting-IP / X-Forwarded-For headers; direct LAN clients have no proxy
    and fall through to the socket peer. A LAN client could spoof the header,
    which is accepted: LAN deployments are trusted, public traffic always
    crosses the tunnel (which overwrites these headers)."""
    fwd = ws.headers.get("cf-connecting-ip") or ws.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return ws.client.host if ws.client else "unknown"


@router.websocket("/ws/scribe")
async def scribe_ws(ws: WebSocket) -> None:
    await ws.accept()
    # Concurrency caps: bound in-flight sessions so a burst can't open unlimited
    # WAV writers or grow an unbounded queue behind the shared ASR/note locks
    # (global cap), and so one visitor can't hold every slot and lock out a
    # another clinic visitor (per-IP cap). Single-threaded asyncio => the checks and
    # increments below are atomic (no await between them). 0 = unlimited.
    state = ws.app.state
    cap = settings.max_concurrent_sessions
    active = getattr(state, "active_sessions", 0)
    if cap and active >= cap:
        busy = ErrorMessage(code="BUSY", message="server at capacity, try again shortly")
        await ws.send_text(busy.model_dump_json())
        await ws.close()
        return

    ip = _client_ip(ws)
    ip_cap = settings.max_sessions_per_ip
    by_ip: dict[str, int] = getattr(state, "sessions_by_ip", None) or {}
    state.sessions_by_ip = by_ip
    if ip_cap and by_ip.get(ip, 0) >= ip_cap:
        limited = ErrorMessage(
            code="IP_LIMIT",
            message="too many active sessions from your connection, close one first",
        )
        await ws.send_text(limited.model_dump_json())
        await ws.close()
        return

    state.active_sessions = active + 1
    by_ip[ip] = by_ip.get(ip, 0) + 1

    asr = getattr(state, "asr_engine", None)
    note_generator = getattr(state, "note_generator", None)
    # Process-wide locks so concurrent sessions don't call the shared (non-reentrant)
    # WhisperModel / note LLM at the same time. Created once in the app lifespan.
    asr_lock = getattr(state, "asr_lock", None)
    note_lock = getattr(state, "note_lock", None)
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
        max_recording_seconds=settings.max_recording_seconds,
    )
    try:
        await session.run()
    finally:
        state.active_sessions = getattr(state, "active_sessions", 1) - 1
        # Drop the entry at zero so the dict doesn't grow one key per visitor ever.
        remaining = by_ip.get(ip, 1) - 1
        if remaining > 0:
            by_ip[ip] = remaining
        else:
            by_ip.pop(ip, None)
