"""WS note flow: Stop -> batch transcribe -> note_done, WAV deleted (PDPA).

Stubs ASR and the note generator so it runs without models. The note generator
returns the sum_v1 text-wrapper shape ({soap_text: ...}) that the live llama-cpp
path produces.
"""

import json
import math
import struct

from fastapi import FastAPI
from fastapi.testclient import TestClient

from medicscribe_server.asr.base import Segment
from medicscribe_server.config import settings
from medicscribe_server.ws import router as ws_router


class StubASR:
    def transcribe(self, pcm, sample_rate):
        return [Segment(text="I have a fever", lang="en", t0=0.0, t1=1.0)]

    def close(self):
        pass


class StubNoteGen:
    def __init__(self, fail=False):
        self.fail = fail
        self.seen_transcript = None

    def generate(self, transcript):
        from medicscribe_server.notes.generator import NoteGenerationError
        self.seen_transcript = transcript
        if self.fail:
            raise NoteGenerationError("boom")
        # sum_v1 text-wrapper shape (matches the live path).
        return {"soap_text": "S: Fever.\nO: Not documented.\nA: Viral fever.\nP: Rest."}


def _pcm(seconds, sr=16000):
    n = int(seconds * sr)
    return struct.pack("<" + "h" * n, *[int(20000 * math.sin(i / 5)) for i in range(n)])


def _make_client(tmp_path, monkeypatch, note_gen):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    monkeypatch.setattr(settings, "audio_dir", audio_dir)
    app = FastAPI()
    app.state.asr_engine = StubASR()
    app.state.note_generator = note_gen
    app.include_router(ws_router.router)
    return TestClient(app), audio_dir


def _run_session(client, session_id):
    pcm = _pcm(1.0)
    messages = []
    with client.websocket_connect("/ws/scribe") as ws:
        ws.send_text(json.dumps({"type": "start", "session_id": session_id}))
        ws.receive_text()  # ack
        for i in range(0, len(pcm), 640):
            ws.send_bytes(pcm[i:i + 640])
        ws.send_text(json.dumps({"type": "stop"}))
        for _ in range(60):
            try:
                messages.append(json.loads(ws.receive_text()))
            except Exception:
                break
    return messages


def test_stop_generates_note_and_deletes_wav(tmp_path, monkeypatch):
    gen = StubNoteGen()
    client, audio_dir = _make_client(tmp_path, monkeypatch, gen)
    messages = _run_session(client, "s-note-1")
    done = [m for m in messages if m["type"] == "note_done"]
    assert done, f"expected note_done, got {[m['type'] for m in messages]}"
    assert done[0]["note"]["soap_text"].startswith("S: Fever")
    assert "I have a fever" in done[0]["raw_transcript"]
    assert "I have a fever" in gen.seen_transcript
    # PDPA: WAV deleted at stop
    assert list(audio_dir.glob("*.wav")) == []


def test_note_failure_sends_error_and_wav_still_deleted(tmp_path, monkeypatch):
    client, audio_dir = _make_client(tmp_path, monkeypatch, StubNoteGen(fail=True))
    messages = _run_session(client, "s-note-2")
    assert any(m["type"] == "error" and m["code"] == "NOTE_FAILED" for m in messages)
    assert list(audio_dir.glob("*.wav")) == []


def test_audio_deleted_emitted_before_note(tmp_path, monkeypatch):
    client, audio_dir = _make_client(tmp_path, monkeypatch, StubNoteGen())
    messages = _run_session(client, "s-note-3")
    types = [m["type"] for m in messages]
    # Server confirms deletion to the client (powers the privacy receipt).
    assert "audio_deleted" in types
    # And it must arrive before the note — audio is gone before note-gen runs.
    assert types.index("audio_deleted") < types.index("note_done")
    deleted = next(m for m in messages if m["type"] == "audio_deleted")
    assert deleted["session_id"] == "s-note-3"
