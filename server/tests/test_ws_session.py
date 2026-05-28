import json
import math
import struct

import pytest
from fastapi.testclient import TestClient

from medicscribe_server.config import settings
from medicscribe_server.main import app


@pytest.fixture
def tmp_audio_dir(tmp_path, monkeypatch):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    monkeypatch.setattr(settings, "audio_dir", audio_dir)
    # Phase 1 tests run WAV-only — never load the 6 GB whisper model.
    monkeypatch.setattr(settings, "asr_enabled", False)
    yield audio_dir


def synthetic_pcm(seconds: float, freq: int = 440, sample_rate: int = 16000) -> bytes:
    n = int(seconds * sample_rate)
    samples = [int(32767 * 0.3 * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n)]
    return struct.pack("<" + "h" * n, *samples)


def test_ws_records_one_second_pcm(tmp_audio_dir):
    client = TestClient(app)
    session_id = "test-session-123"
    pcm = synthetic_pcm(1.0)
    with client.websocket_connect("/ws/scribe") as ws:
        ws.send_text(json.dumps({"type": "start", "session_id": session_id}))
        ack = json.loads(ws.receive_text())
        assert ack["type"] == "ack"
        assert ack["session_id"] == session_id
        frame_size = 640
        for i in range(0, len(pcm), frame_size):
            ws.send_bytes(pcm[i : i + frame_size])
        ws.send_text(json.dumps({"type": "stop"}))
    # PDPA: WAV is deleted at stop; no audio persists after the session ends.
    wav_path = tmp_audio_dir / f"{session_id}.wav"
    assert not wav_path.exists()


def test_ws_invalid_message_returns_error(tmp_audio_dir):
    client = TestClient(app)
    with client.websocket_connect("/ws/scribe") as ws:
        ws.send_text('{"type":"start"}')
        err = json.loads(ws.receive_text())
        assert err["type"] == "error"
        assert err["code"] == "INVALID_MESSAGE"
