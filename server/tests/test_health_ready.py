from fastapi import FastAPI
from fastapi.testclient import TestClient

from medicscribe_server.api import health
from medicscribe_server.config import settings


class _ASR:
    pass


class _Gen:
    def __init__(self, ok: bool) -> None:
        self._ok = ok

    def healthy(self) -> bool:
        return self._ok


def _client(asr, gen, monkeypatch) -> TestClient:
    monkeypatch.setattr(settings, "asr_enabled", True)
    monkeypatch.setattr(settings, "note_enabled", True)
    app = FastAPI()
    app.state.asr_engine = asr
    app.state.note_generator = gen
    app.include_router(health.router)
    return TestClient(app)


def test_ready_when_asr_and_note_up(monkeypatch):
    c = _client(_ASR(), _Gen(True), monkeypatch)
    r = c.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body == {"ready": True, "asr": True, "note_llm": True}


def test_not_ready_when_note_llm_down(monkeypatch):
    c = _client(_ASR(), _Gen(False), monkeypatch)
    r = c.get("/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["ready"] is False
    assert body["asr"] is True
    assert body["note_llm"] is False


def test_not_ready_when_asr_missing(monkeypatch):
    c = _client(None, _Gen(True), monkeypatch)
    r = c.get("/health/ready")
    assert r.status_code == 503
    assert r.json()["asr"] is False
