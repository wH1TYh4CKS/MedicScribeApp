from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field


class StartMessage(BaseModel):
    type: Literal["start"]
    session_id: str
    template: str = "soap_v1"
    languages: list[str] = Field(default_factory=lambda: ["en", "zh", "ms", "ta"])


class StopMessage(BaseModel):
    type: Literal["stop"]


ClientMessage = Annotated[
    Union[StartMessage, StopMessage],
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
    Union[AckMessage, TranscriptPartial, TranscriptFinal, NoteProgress, NoteDone, ErrorMessage],
    Field(discriminator="type"),
]
