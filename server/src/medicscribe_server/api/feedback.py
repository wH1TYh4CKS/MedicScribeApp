import json
import time
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from medicscribe_server.config import settings

router = APIRouter()


class FeedbackIn(BaseModel):
    """One feedback submission. All fields optional so a user can send
    just a rating, or just a note. NOT a consultation — the page warns: no PHI."""

    rating: int | None = Field(default=None, ge=1, le=5)
    role: str = ""        # doctor / nurse / admin / other
    liked: str = ""       # what worked
    issues: str = ""      # what broke / annoyed
    would_pay: str = ""   # pricing / willingness signal
    contact: str = ""     # optional email/phone for follow-up


def _clip(text: str) -> str:
    """Trim and cap one field so a huge paste can't fill the disk."""
    return text.strip()[: settings.feedback_field_max_chars]


def _entry_from(body: FeedbackIn) -> dict:
    """Shape one submission into a timestamped record."""
    return {
        "ts": int(time.time()),
        "rating": body.rating,
        "role": _clip(body.role),
        "liked": _clip(body.liked),
        "issues": _clip(body.issues),
        "would_pay": _clip(body.would_pay),
        "contact": _clip(body.contact),
    }


def _append_jsonl(entry: dict) -> None:
    """Append one record to the feedback log (one JSON object per line)."""
    settings.feedback_dir.mkdir(parents=True, exist_ok=True)
    path: Path = settings.feedback_dir / "feedback.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@router.post("/api/feedback")
async def submit_feedback(body: FeedbackIn) -> dict:
    """Store feedback locally. Product feedback only; no PHI, no DB, no egress."""
    _append_jsonl(_entry_from(body))
    return {"ok": True}
