from __future__ import annotations

import asyncio
import logging
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, TypeAdapter, ValidationError

from medicscribe_server.store.audio_writer import WavWriter, read_wav_pcm
from medicscribe_server.ws.protocol import (
    AckMessage,
    AudioDeleted,
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
    from medicscribe_server.notes.generator import NoteGenerator

logger = logging.getLogger(__name__)
_CLIENT_ADAPTER: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)


class SessionPhase(StrEnum):
    INIT = "init"
    RECORDING = "recording"
    STOPPED = "stopped"


class WSSession:
    def __init__(
        self,
        ws: WebSocket,
        audio_dir: Path,
        sample_rate: int = 16000,
        asr: ASREngine | None = None,
        note_generator: NoteGenerator | None = None,
        asr_lock: asyncio.Lock | None = None,
        note_lock: asyncio.Lock | None = None,
        max_recording_seconds: int = 0,
    ) -> None:
        self.ws = ws
        self.audio_dir = audio_dir
        self.sample_rate = sample_rate
        # Hard cap on audio written to disk, computed from a max duration. Bounds the
        # WAV regardless of how fast a client streams (an abusive client can push PCM
        # far faster than realtime), so it is a disk-DoS guard, not just a UX limit.
        # 0 = unlimited. int16 mono => 2 bytes/sample.
        self._max_bytes = max_recording_seconds * sample_rate * 2 if max_recording_seconds else 0
        self.asr = asr
        self.note_generator = note_generator
        self.phase: SessionPhase = SessionPhase.INIT
        self.writer: WavWriter | None = None
        self.session_id: str | None = None
        self.wav_path: Path | None = None
        self.transcript_lines: list[str] = []
        self.bytes_written = 0
        # Carry a dangling byte when a binary frame splits an int16 sample, so the
        # WAV stays 2-byte aligned no matter how the client chunks the stream
        # (a misaligned write garbles every following sample).
        self._pcm_carry = b""
        # Batch-at-Stop: the whole consult is transcribed once at Stop with full
        # context (read back from the on-disk WAV — see _on_stop). Per-utterance
        # streaming made large-v3 hallucinate on tiny chunks, and the redesigned UI
        # shows no live transcript, so we no longer hold a second copy of the audio
        # in RAM.
        # Serialize whisper calls — the engine is not safe under concurrent use.
        # The locks MUST be shared across sessions: the ASR engine and the note LLM
        # are process-wide singletons, so a per-session lock would let two consults
        # hit the same model at once. The router passes the shared locks; fall back
        # to private ones only when nothing is wired (tests / WAV-only mode).
        self._asr_lock = asr_lock or asyncio.Lock()
        self._note_lock = note_lock or asyncio.Lock()

    @property
    def _transcribing(self) -> bool:
        return self.asr is not None

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
        # Defense-in-depth (the StartMessage pattern is the primary guard): never
        # let the WAV path escape audio_dir, even if that validation is loosened.
        if self.audio_dir.resolve() not in self.wav_path.resolve().parents:
            self.wav_path = None
            await self._send_error("INVALID_MESSAGE", "invalid session_id")
            return
        self.writer = WavWriter(self.wav_path, sample_rate=self.sample_rate)
        self.phase = SessionPhase.RECORDING
        logger.info("Session %s recording -> %s", self.session_id, self.wav_path)
        await self._send(AckMessage(session_id=self.session_id))

    async def _on_pcm(self, data: bytes) -> None:
        if self.phase != SessionPhase.RECORDING or self.writer is None:
            logger.warning("Dropping %d bytes PCM in phase=%s", len(data), self.phase.value)
            return
        # Keep int16 alignment across arbitrary frame boundaries (carry odd byte).
        if self._pcm_carry:
            data = self._pcm_carry + data
            self._pcm_carry = b""
        if len(data) & 1:
            self._pcm_carry = data[-1:]
            data = data[:-1]
        if not data:
            return
        self.writer.write(data)
        self.bytes_written += len(data)
        # No RAM buffer: the WAV on disk is the single copy; it is read back once
        # at Stop for transcription (see _on_stop).
        # Enforce the recording cap. Past the limit we abort (no note) rather than
        # transcribe an over-long/abusive stream — and STOPPED makes run() finalize,
        # deleting the WAV. The pattern-validated session_id already prevents path
        # abuse; this prevents disk-fill abuse.
        if self._max_bytes and self.bytes_written >= self._max_bytes:
            logger.warning(
                "Session %s hit recording cap (%d bytes)", self.session_id, self._max_bytes
            )
            await self._send_error("LIMIT_EXCEEDED", "recording too long")
            self.phase = SessionPhase.STOPPED

    async def _transcribe_and_send(self, pcm: bytes) -> None:
        assert self.asr is not None
        async with self._asr_lock:
            segments = await asyncio.to_thread(self.asr.transcribe, pcm, self.sample_rate)
        for seg in segments:
            self.transcript_lines.append(seg.text)
            await self._send(TranscriptFinal(text=seg.text, lang=seg.lang, t=seg.t0))

    async def _on_stop(self) -> None:
        # Close + flush the WAV first so it can be read back for transcription.
        if self.writer is not None:
            duration = self.writer.duration_seconds()
            self.writer.close()
            self.writer = None
            logger.info(
                "Session %s stopped. bytes=%d duration=%.2fs",
                self.session_id,
                self.bytes_written,
                duration,
            )
        # Transcribe the whole consult in one pass from the on-disk WAV — full
        # context, whisper's own VAD segments it (asr.yaml vad_filter: true).
        if self._transcribing and self.wav_path is not None and self.wav_path.exists():
            pcm = read_wav_pcm(self.wav_path)
            if pcm:
                try:
                    await self._transcribe_and_send(pcm)
                except Exception as exc:  # CUDA OOM, runtime, degenerate audio
                    # Don't die silently — tell the client and clean up the audio.
                    logger.warning(
                        "ASR failed for session %s: %s", self.session_id, type(exc).__name__
                    )
                    self._delete_wav()
                    if self.session_id is not None:
                        await self._send(AudioDeleted(session_id=self.session_id))
                    await self._send_error("ASR_FAILED", "Transcription failed")
                    self.phase = SessionPhase.STOPPED
                    return
        # PDPA: note-gen uses the transcript text, not the audio. Delete the WAV now.
        self._delete_wav()
        # Tell the client the audio is gone so the app can show a real, server-
        # confirmed deletion timestamp in its privacy receipt (not a UI claim).
        if self.session_id is not None:
            await self._send(AudioDeleted(session_id=self.session_id))
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
        # No speech recognised (silence / too short). Tell the client so its UI
        # leaves the "Generating…" state instead of hanging forever.
        if self._transcribing and not transcript:
            await self._send_error("NO_SPEECH", "No speech detected. Please try again.")
            return
        if self.note_generator is None or not transcript:
            return
        await self._send(NoteProgress(stage="generating", pct=50))
        try:
            # Serialize note-gen too — the LLM client / GPU model is shared.
            async with self._note_lock:
                note = await asyncio.to_thread(self.note_generator.generate, transcript)
        except Exception as exc:  # NoteGenerationError and anything unexpected
            logger.warning(
                "note generation failed for session %s: %s", self.session_id, type(exc).__name__
            )
            await self._send_error("NOTE_FAILED", "Note generation failed")
            return
        await self._send(NoteDone(note=note, raw_transcript=transcript))

    async def _send(self, msg: BaseModel) -> None:
        await self.ws.send_text(msg.model_dump_json())

    async def _send_error(self, code: str, message: str) -> None:
        # Deliberately does NOT change phase: a recoverable error (duplicate start,
        # one malformed text frame) must not flip a live recording out of RECORDING
        # — that silently drops every later PCM frame (truncated consult). Fatal
        # paths (LIMIT_EXCEEDED, ASR_FAILED) set STOPPED themselves at the call site.
        try:
            await self._send(ErrorMessage(code=code, message=message))
        except Exception:
            logger.exception("Failed to send error to client")

    def _finalize(self) -> None:
        """Always-run cleanup (run() finally). Closes/deletes the WAV and wipes the
        in-memory transcript so nothing outlives the connection. The note is never
        stored on the session — it is streamed straight to the client — so there is
        nothing else to wipe. PDPA: the server keeps zero consultation data after
        the session ends."""
        if self.writer is not None:
            try:
                self.writer.close()
            except Exception:
                logger.exception("Failed to close writer in finalize")
            self.writer = None
        self._delete_wav()
        # Explicit PHI wipe — do not rely on GC timing.
        self.transcript_lines = []
        self.bytes_written = 0
        logger.info("Session %s purged (audio + transcript cleared)", self.session_id)
