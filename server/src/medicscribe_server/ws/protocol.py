from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class StartMessage(BaseModel):
    type: Literal["start"]
    # session_id is used to build the on-disk WAV path — constrain to a safe slug
    # (no '/', '.', whitespace) so it can never traverse out of audio_dir (CWE-22).
    # Browser/Android send a UUID, which matches this.
    session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    template: str = "soap_v1"
    languages: list[str] = Field(default_factory=lambda: ["en", "zh", "ms", "ta"])


class StopMessage(BaseModel):
    type: Literal["stop"]


ClientMessage = Annotated[
    StartMessage | StopMessage,
    Field(discriminator="type"),
]


class AckMessage(BaseModel):
    type: Literal["ack"] = "ack"
    session_id: str


class TranscriptPartial(BaseModel):
    type: Literal["transcript_partial"] = "transcript_partial"
    text: str
    speaker: str | None = None
    lang: str | None = None
    t: float


class TranscriptFinal(BaseModel):
    type: Literal["transcript_final"] = "transcript_final"
    text: str
    speaker: str | None = None
    lang: str | None = None
    t: float


class AudioDeleted(BaseModel):
    type: Literal["audio_deleted"] = "audio_deleted"
    session_id: str


class NoteProgress(BaseModel):
    type: Literal["note_progress"] = "note_progress"
    stage: str
    pct: int


class NoteDone(BaseModel):
    type: Literal["note_done"] = "note_done"
    note: dict[str, Any]
    raw_transcript: str


class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str


ServerMessage = Annotated[
    AckMessage
    | TranscriptPartial
    | TranscriptFinal
    | AudioDeleted
    | NoteProgress
    | NoteDone
    | ErrorMessage,
    Field(discriminator="type"),
]
