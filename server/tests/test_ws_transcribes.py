"""WS wiring test: PCM stream is buffered, then transcribed once at Stop.

Batch-at-Stop architecture: the server no longer transcribes per-utterance while
recording. It buffers the whole consult and makes a single ASR call at Stop (with
whisper's own vad_filter segmenting the long audio). Uses a stub ASR so it runs in
milliseconds with no model download; whisper quality is covered by the slow
`test_asr_engine.py`.
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
    """Records each transcribe() call so the test can prove batch-at-Stop:
    one call, receiving the full buffered consult — not many small calls."""

    def __init__(self) -> None:
        self.call_sizes: list[int] = []

    def transcribe(self, pcm: bytes, sample_rate: int) -> list[Segment]:
        self.call_sizes.append(len(pcm))
        return [Segment(text="hello world", lang="en", t0=0.0, t1=1.0)]

    def close(self) -> None:
        pass


@pytest.fixture
def stub_asr():
    return StubASR()


@pytest.fixture
def transcribe_client(tmp_path, monkeypatch, stub_asr):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    monkeypatch.setattr(settings, "audio_dir", audio_dir)
    app = FastAPI()
    app.state.asr_engine = stub_asr
    app.state.note_generator = None
    app.include_router(ws_router.router)
    return TestClient(app)


def synthetic_pcm(seconds: float, freq: int = 440, sample_rate: int = 16000) -> bytes:
    n = int(seconds * sample_rate)
    samples = [int(32767 * 0.3 * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n)]
    return struct.pack("<" + "h" * n, *samples)


def test_ws_buffers_then_transcribes_once_at_stop(transcribe_client, stub_asr):
    pcm = synthetic_pcm(1.0)  # 32000 bytes
    finals = []
    with transcribe_client.websocket_connect("/ws/scribe") as ws:
        ws.send_text(json.dumps({"type": "start", "session_id": "t-asr-1"}))
        assert json.loads(ws.receive_text())["type"] == "ack"
        frame_size = 640
        for i in range(0, len(pcm), frame_size):
            ws.send_bytes(pcm[i : i + frame_size])
        # No transcription should have happened yet — audio is only buffered.
        assert stub_asr.call_sizes == [], "ASR must not run mid-stream (batch-at-Stop)"
        ws.send_text(json.dumps({"type": "stop"}))
        # Drain server messages until it closes (bounded so a regression can't hang).
        for _ in range(50):
            try:
                msg = json.loads(ws.receive_text())
            except Exception:
                break
            if msg["type"] == "transcript_final":
                finals.append(msg)

    # Exactly one ASR call, fed the entire buffered consult.
    assert stub_asr.call_sizes == [len(pcm)], (
        f"expected one batch call of {len(pcm)} bytes, got {stub_asr.call_sizes}"
    )
    assert finals, "expected at least one transcript_final"
    assert finals[0]["text"] == "hello world"
    assert finals[0]["lang"] == "en"
