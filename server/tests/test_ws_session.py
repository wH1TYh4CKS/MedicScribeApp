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


def test_ws_rejects_path_traversal_session_id(tmp_audio_dir, tmp_path):
    # CWE-22: session_id is used to build the on-disk WAV path. A traversal id
    # must be rejected, never written outside audio_dir.
    client = TestClient(app)
    evil = "../../../../" + str(tmp_path / "pwned")  # would land at <tmp_path>/pwned.wav
    with client.websocket_connect("/ws/scribe") as ws:
        ws.send_text(json.dumps({"type": "start", "session_id": evil}))
        err = json.loads(ws.receive_text())
        assert err["type"] == "error"
        assert err["code"] == "INVALID_MESSAGE"
    # Nothing written outside the audio dir.
    assert not (tmp_path / "pwned.wav").exists()


def test_ws_odd_length_frames_stay_aligned(tmp_audio_dir):
    # Odd-length binary frames must not crash the session or misalign the WAV.
    client = TestClient(app)
    pcm = synthetic_pcm(1.0)
    msgs = []
    with client.websocket_connect("/ws/scribe") as ws:
        ws.send_text(json.dumps({"type": "start", "session_id": "odd-frames"}))
        assert json.loads(ws.receive_text())["type"] == "ack"
        for i in range(0, len(pcm), 641):  # odd chunk size
            ws.send_bytes(pcm[i : i + 641])
        ws.send_text(json.dumps({"type": "stop"}))
        for _ in range(5):
            try:
                msgs.append(json.loads(ws.receive_text()))
            except Exception:
                break
    assert any(m["type"] == "audio_deleted" for m in msgs), msgs
    assert not (tmp_audio_dir / "odd-frames.wav").exists()


def test_ws_concurrency_cap_rejects_when_busy(tmp_audio_dir, monkeypatch):
    # Cap at 1: a second concurrent session is rejected with BUSY.
    monkeypatch.setattr(settings, "max_concurrent_sessions", 1)
    monkeypatch.setattr(app.state, "active_sessions", 0, raising=False)
    client = TestClient(app)
    with client.websocket_connect("/ws/scribe") as ws1:
        ws1.send_text(json.dumps({"type": "start", "session_id": "busy-a"}))
        assert json.loads(ws1.receive_text())["type"] == "ack"
        with client.websocket_connect("/ws/scribe") as ws2:
            msg = json.loads(ws2.receive_text())
            assert msg["type"] == "error" and msg["code"] == "BUSY", msg


def test_ws_per_ip_cap_rejects_same_ip_allows_other_ip(tmp_audio_dir, monkeypatch):
    # Per-IP cap 1: a second concurrent session from the same visitor IP gets
    # IP_LIMIT, while a different IP still gets through. The visitor IP arrives in
    # the Cloudflare tunnel's CF-Connecting-IP header (socket peer is localhost).
    monkeypatch.setattr(settings, "max_sessions_per_ip", 1)
    monkeypatch.setattr(app.state, "sessions_by_ip", {}, raising=False)
    client = TestClient(app)
    hdr_a = {"cf-connecting-ip": "203.0.113.7"}
    hdr_b = {"cf-connecting-ip": "203.0.113.8"}
    with client.websocket_connect("/ws/scribe", headers=hdr_a) as ws1:
        ws1.send_text(json.dumps({"type": "start", "session_id": "ipcap-a"}))
        assert json.loads(ws1.receive_text())["type"] == "ack"
        with client.websocket_connect("/ws/scribe", headers=hdr_a) as ws2:
            msg = json.loads(ws2.receive_text())
            assert msg["type"] == "error" and msg["code"] == "IP_LIMIT", msg
        with client.websocket_connect("/ws/scribe", headers=hdr_b) as ws3:
            ws3.send_text(json.dumps({"type": "start", "session_id": "ipcap-b"}))
            assert json.loads(ws3.receive_text())["type"] == "ack"


def test_ws_per_ip_cap_releases_slot_on_disconnect(tmp_audio_dir, monkeypatch):
    # Closing a session frees its per-IP slot — same IP can connect again.
    monkeypatch.setattr(settings, "max_sessions_per_ip", 1)
    monkeypatch.setattr(app.state, "sessions_by_ip", {}, raising=False)
    client = TestClient(app)
    hdr = {"cf-connecting-ip": "203.0.113.9"}
    with client.websocket_connect("/ws/scribe", headers=hdr) as ws1:
        ws1.send_text(json.dumps({"type": "start", "session_id": "iprel-a"}))
        assert json.loads(ws1.receive_text())["type"] == "ack"
    with client.websocket_connect("/ws/scribe", headers=hdr) as ws2:
        ws2.send_text(json.dumps({"type": "start", "session_id": "iprel-b"}))
        assert json.loads(ws2.receive_text())["type"] == "ack"
    assert app.state.sessions_by_ip == {}


def test_ws_recording_cap_aborts_and_deletes(tmp_audio_dir, monkeypatch):
    # Cap at 1s (32000 bytes). Stream 2s of PCM -> LIMIT_EXCEEDED, WAV deleted, no note.
    monkeypatch.setattr(settings, "max_recording_seconds", 1)
    client = TestClient(app)
    pcm = synthetic_pcm(2.0)
    got = []
    with client.websocket_connect("/ws/scribe") as ws:
        ws.send_text(json.dumps({"type": "start", "session_id": "cap-test"}))
        assert json.loads(ws.receive_text())["type"] == "ack"
        try:
            for i in range(0, len(pcm), 640):
                ws.send_bytes(pcm[i : i + 640])
            for _ in range(5):
                got.append(json.loads(ws.receive_text()))
        except Exception:
            pass
    assert any(m.get("code") == "LIMIT_EXCEEDED" for m in got), got
    assert not (tmp_audio_dir / "cap-test.wav").exists()


class _FakeWS:
    """Duck-typed WebSocket capturing server messages for unit-level session tests."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


def test_duplicate_start_does_not_kill_recording(tmp_audio_dir):
    # A stray duplicate "start" mid-recording must answer ALREADY_STARTED but leave
    # the session in RECORDING — flipping it out silently drops every later PCM
    # frame (truncated consult).
    import asyncio

    from medicscribe_server.ws.session import SessionPhase, WSSession

    async def scenario() -> None:
        ws = _FakeWS()
        s = WSSession(ws=ws, audio_dir=tmp_audio_dir)
        await s._on_text(json.dumps({"type": "start", "session_id": "dup"}))
        assert s.phase == SessionPhase.RECORDING
        await s._on_text(json.dumps({"type": "start", "session_id": "dup"}))
        assert any(m.get("code") == "ALREADY_STARTED" for m in ws.sent)
        assert s.phase == SessionPhase.RECORDING
        await s._on_pcm(b"\x00\x00" * 160)
        assert s.bytes_written == 320
        s._finalize()

    asyncio.run(scenario())


def test_malformed_text_does_not_kill_recording(tmp_audio_dir):
    # One malformed text frame mid-recording must answer INVALID_MESSAGE but keep
    # accepting audio.
    import asyncio

    from medicscribe_server.ws.session import SessionPhase, WSSession

    async def scenario() -> None:
        ws = _FakeWS()
        s = WSSession(ws=ws, audio_dir=tmp_audio_dir)
        await s._on_text(json.dumps({"type": "start", "session_id": "garbled"}))
        assert s.phase == SessionPhase.RECORDING
        await s._on_text("not json at all")
        assert any(m.get("code") == "INVALID_MESSAGE" for m in ws.sent)
        assert s.phase == SessionPhase.RECORDING
        await s._on_pcm(b"\x00\x00" * 160)
        assert s.bytes_written == 320
        s._finalize()

    asyncio.run(scenario())


def test_ws_rejects_slash_and_dot_session_ids(tmp_audio_dir):
    client = TestClient(app)
    for bad in ["a/b", "..", "x.y", "with space", ""]:
        with client.websocket_connect("/ws/scribe") as ws:
            ws.send_text(json.dumps({"type": "start", "session_id": bad}))
            err = json.loads(ws.receive_text())
            assert err["type"] == "error", f"{bad!r} should be rejected"
            assert err["code"] == "INVALID_MESSAGE"
