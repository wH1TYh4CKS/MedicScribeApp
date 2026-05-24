"""Phase 2 wiring test: PCM stream -> endpointer -> ASR -> transcript_final.

Uses stubs for the endpointer and ASR engine so it runs in milliseconds with no
model download. Verifies the WS plumbing, not whisper quality (that is covered by
the slow `test_asr_engine.py`).
"""

import json
import math
import struct

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from medicscribe_server.asr.base import Segment
from medicscribe_server.config import settings
from medicscribe_server.ws import router as ws_router


class StubASR:
    def transcribe(self, pcm: bytes, sample_rate: int) -> list[Segment]:
        return [Segment(text="hello world", lang="en", t0=0.0, t1=1.0)]

    def close(self) -> None:
        pass


class StubEndpointer:
    """Emits one utterance once it has seen >= threshold bytes; flush drains rest."""

    def __init__(self, threshold_bytes: int = 16000) -> None:
        self._threshold = threshold_bytes
        self._buf = bytearray()
        self._ready: list[bytes] = []

    def accept(self, frame: bytes) -> None:
        self._buf.extend(frame)
        if len(self._buf) >= self._threshold:
            self._ready.append(bytes(self._buf))
            self._buf = bytearray()

    def pop_utterance(self) -> bytes | None:
        return self._ready.pop(0) if self._ready else None

    def flush(self) -> bytes | None:
        tail = bytes(self._buf) if self._buf else None
        self._buf = bytearray()
        return tail


@pytest.fixture
def transcribe_client(tmp_path, monkeypatch):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    monkeypatch.setattr(settings, "audio_dir", audio_dir)
    app = FastAPI()
    app.state.asr_engine = StubASR()
    app.state.make_endpointer = lambda: StubEndpointer()
    app.include_router(ws_router.router)
    return TestClient(app)


def synthetic_pcm(seconds: float, freq: int = 440, sample_rate: int = 16000) -> bytes:
    n = int(seconds * sample_rate)
    samples = [int(32767 * 0.3 * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n)]
    return struct.pack("<" + "h" * n, *samples)


def test_ws_emits_transcript_final(transcribe_client):
    pcm = synthetic_pcm(1.0)  # 32000 bytes -> >= one stub utterance + flushed tail
    finals = []
    with transcribe_client.websocket_connect("/ws/scribe") as ws:
        ws.send_text(json.dumps({"type": "start", "session_id": "t-asr-1"}))
        assert json.loads(ws.receive_text())["type"] == "ack"
        frame_size = 640
        for i in range(0, len(pcm), frame_size):
            ws.send_bytes(pcm[i : i + frame_size])
        ws.send_text(json.dumps({"type": "stop"}))
        # Drain server messages until it closes (bounded so a regression can't hang).
        for _ in range(50):
            try:
                msg = json.loads(ws.receive_text())
            except Exception:
                break
            if msg["type"] == "transcript_final":
                finals.append(msg)
    assert finals, "expected at least one transcript_final"
    assert finals[0]["text"] == "hello world"
    assert finals[0]["lang"] == "en"
