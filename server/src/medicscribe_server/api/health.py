import subprocess
from pathlib import Path

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from medicscribe_server.config import settings

router = APIRouter()


def _fs_type(path: Path) -> str:
    """Filesystem type backing `path` (longest matching mount in /proc/mounts).
    'tmpfs'/'ramfs' => audio lives in RAM, never on persistent disk."""
    try:
        target = str(path.resolve())
        best, best_fs = "", "unknown"
        for line in Path("/proc/mounts").read_text().splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            mp, fs = parts[1], parts[2]
            if (target == mp or target.startswith(mp.rstrip("/") + "/")) and len(mp) > len(best):
                best, best_fs = mp, fs
        return best_fs
    except OSError:
        return "unknown"


# Deployed code commit — links the running server to the auditable source so a
# client's "show me the code" verifies the exact binary that handled their consult.
# Resolved once at import; null outside a git checkout.
try:
    _COMMIT = subprocess.run(
        ["git", "-C", str(Path(__file__).resolve().parent), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, timeout=2,
    ).stdout.strip() or None
except (OSError, subprocess.SubprocessError):
    _COMMIT = None


class HealthResponse(BaseModel):
    status: str
    version: str


class ReadyResponse(BaseModel):
    ready: bool
    asr: bool
    note_llm: bool


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness — the web process is up (does not check the models)."""
    return HealthResponse(status="ok", version=settings.app_version)


@router.get("/health/ready", response_model=ReadyResponse)
async def ready(request: Request, response: Response) -> ReadyResponse:
    """Readiness — are the things a consult actually needs up? ASR model loaded
    and the note LLM backend reachable. Powers the page's status indicator and
    fleet monitoring. 200 when ready, 503 otherwise (body carries the detail)."""
    state = request.app.state
    asr_ok = (not settings.asr_enabled) or getattr(state, "asr_engine", None) is not None

    note_gen = getattr(state, "note_generator", None)
    if not settings.note_enabled:
        note_ok = True
    else:
        note_ok = note_gen is not None and note_gen.healthy()

    is_ready = asr_ok and note_ok
    if not is_ready:
        response.status_code = 503
    return ReadyResponse(ready=is_ready, asr=asr_ok, note_llm=note_ok)


class TransparencyResponse(BaseModel):
    audio_retention: str
    audio_files_now: int
    audio_storage: str
    recording_ttl_seconds: int
    transcript_storage: str
    note_storage: str
    database: bool
    cloud_egress: bool
    source_commit: str | None


@router.get("/transparency", response_model=TransparencyResponse)
async def transparency() -> TransparencyResponse:
    """Client-verifiable privacy receipt. Anyone (the clinic) can hit this
    live and check what the box keeps. `audio_files_now` is a real-time count of
    WAVs on disk — it should read 0 between consults. `audio_storage` reads 'tmpfs'
    when audio is RAM-backed (never persisted). Pair with the per-consult
    `audio_deleted` WS receipt and the open source at `source_commit`."""
    try:
        files_now = sum(1 for _ in settings.audio_dir.glob("*.wav"))
    except OSError:
        files_now = -1
    return TransparencyResponse(
        audio_retention="deleted immediately after transcription",
        audio_files_now=files_now,
        audio_storage=_fs_type(settings.audio_dir),
        recording_ttl_seconds=settings.recording_ttl_seconds,
        transcript_storage="in-memory only, wiped when the connection closes",
        note_storage="streamed to the client, never stored server-side",
        database=False,
        cloud_egress=False,
        source_commit=_COMMIT,
    )
