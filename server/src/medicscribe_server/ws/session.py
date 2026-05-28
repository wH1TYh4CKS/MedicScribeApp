from __future__ import annotations

import asyncio
import logging
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, TypeAdapter, ValidationError

from medicscribe_server.store.audio_writer import WavWriter
from medicscribe_server.ws.protocol import (
    AckMessage,
    ClientMessage,
    ErrorMessage,
    NoteDone,
    NoteProgress,
    StartMessage,
    StopMessage,
    TranscriptFinal,
)

if TYPE_CHECKING:
    from medicscribe_server.asr.base import ASREngine
    from medicscribe_server.asr.vad import Endpointer
    from medicscribe_server.notes.generator import NoteGenerator

logger = logging.getLogger(__name__)
_CLIENT_ADAPTER: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


class SessionPhase(str, Enum):
    INIT = "init"
    RECORDING = "recording"
    STOPPED = "stopped"
    ERROR = "error"


class WSSession:
    def __init__(
        self,
        ws: WebSocket,
        audio_dir: Path,
        sample_rate: int = 16000,
        asr: ASREngine | None = None,
        endpointer: Endpointer | None = None,
        note_generator: "NoteGenerator | None" = None,
    ) -> None:
        self.ws = ws
        self.audio_dir = audio_dir
        self.sample_rate = sample_rate
        self.asr = asr
        self.endpointer = endpointer
        self.note_generator = note_generator
        self.phase: SessionPhase = SessionPhase.INIT
        self.writer: WavWriter | None = None
        self.session_id: str | None = None
        self.wav_path: Path | None = None
        self.transcript_lines: list[str] = []
        self.bytes_written = 0
        # Serialize whisper calls — the engine is not safe under concurrent use.
        self._asr_lock = asyncio.Lock()

    @property
    def _transcribing(self) -> bool:
        return self.asr is not None and self.endpointer is not None

    async def run(self) -> None:
        try:
            while True:
                message = await self.ws.receive()
                msg_type = message.get("type")
                if msg_type == "websocket.disconnect":
                    break
                if "text" in message and message["text"] is not None:
                    await self._on_text(message["text"])
                elif "bytes" in message and message["bytes"] is not None:
                    await self._on_pcm(message["bytes"])
                if self.phase == SessionPhase.STOPPED:
                    break
        except WebSocketDisconnect:
            logger.info("Client disconnected (session=%s)", self.session_id)
        finally:
            self._finalize()
            try:
                await self.ws.close()
            except Exception:
                pass

    async def _on_text(self, text: str) -> None:
        try:
            msg = _CLIENT_ADAPTER.validate_json(text)
        except ValidationError as exc:
            await self._send_error("INVALID_MESSAGE", str(exc))
            return
        if isinstance(msg, StartMessage):
            await self._on_start(msg)
        elif isinstance(msg, StopMessage):
            await self._on_stop()

    async def _on_start(self, msg: StartMessage) -> None:
        if self.phase != SessionPhase.INIT:
            await self._send_error("ALREADY_STARTED", "Session already started")
            return
        self.session_id = msg.session_id
        self.wav_path = self.audio_dir / f"{self.session_id}.wav"
        self.writer = WavWriter(self.wav_path, sample_rate=self.sample_rate)
        self.phase = SessionPhase.RECORDING
        logger.info("Session %s recording -> %s", self.session_id, self.wav_path)
        await self._send(AckMessage(session_id=self.session_id))

    async def _on_pcm(self, data: bytes) -> None:
        if self.phase != SessionPhase.RECORDING or self.writer is None:
            logger.warning("Dropping %d bytes PCM in phase=%s", len(data), self.phase.value)
            return
        self.writer.write(data)
        self.bytes_written += len(data)
        if self._transcribing:
            self.endpointer.accept(data)
            await self._drain_transcripts()

    async def _drain_transcripts(self) -> None:
        """Transcribe every completed utterance the endpointer has buffered."""
        assert self.endpointer is not None and self.asr is not None
        while (utt := self.endpointer.pop_utterance()) is not None:
            await self._transcribe_and_send(utt)

    async def _transcribe_and_send(self, pcm: bytes) -> None:
        assert self.asr is not None
        async with self._asr_lock:
            segments = await asyncio.to_thread(self.asr.transcribe, pcm, self.sample_rate)
        for seg in segments:
            self.transcript_lines.append(seg.text)
            await self._send(
                TranscriptFinal(text=seg.text, lang=seg.lang, t=seg.t0)
            )

    async def _on_stop(self) -> None:
        if self._transcribing and self.endpointer is not None:
            tail = self.endpointer.flush()
            if tail:
                await self._transcribe_and_send(tail)
        if self.writer is not None:
            duration = self.writer.duration_seconds()
            self.writer.close()
            self.writer = None
            logger.info(
                "Session %s stopped. bytes=%d duration=%.2fs",
                self.session_id, self.bytes_written, duration,
            )
        # PDPA: note-gen uses the transcript text, not the audio. Delete the WAV now.
        self._delete_wav()
        await self._maybe_generate_note()
        self.phase = SessionPhase.STOPPED

    def _delete_wav(self) -> None:
        if self.wav_path is not None:
            try:
                self.wav_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("could not delete wav for session %s", self.session_id)
            self.wav_path = None

    async def _maybe_generate_note(self) -> None:
        transcript = "\n".join(self.transcript_lines).strip()
        if self.note_generator is None or not transcript:
            return
        await self._send(NoteProgress(stage="generating", pct=50))
        try:
            note = await asyncio.to_thread(self.note_generator.generate, transcript)
        except Exception as exc:  # NoteGenerationError and anything unexpected
            logger.warning("note generation failed for session %s: %s",
                           self.session_id, type(exc).__name__)
            await self._send_error("NOTE_FAILED", "Note generation failed")
            return
        await self._send(NoteDone(note=note, raw_transcript=transcript))

    async def _send(self, msg: BaseModel) -> None:
        await self.ws.send_text(msg.model_dump_json())

    async def _send_error(self, code: str, message: str) -> None:
        self.phase = SessionPhase.ERROR
        try:
            await self._send(ErrorMessage(code=code, message=message))
        except Exception:
            logger.exception("Failed to send error to client")

    def _finalize(self) -> None:
        if self.writer is not None:
            try:
                self.writer.close()
            except Exception:
                logger.exception("Failed to close writer in finalize")
            self.writer = None
        self._delete_wav()
