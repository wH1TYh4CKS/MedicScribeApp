import pytest
from medicscribe_server.llm_client.base import LLMError
from medicscribe_server.llm_client.stub import StubLLMClient

SCHEMA = {"type": "object", "required": ["chief_complaint"],
          "properties": {"chief_complaint": {"type": "string"}}}


def test_stub_returns_default_note():
    c = StubLLMClient()
    note = c.complete_json("any prompt", SCHEMA)
    assert isinstance(note, dict)
    assert "chief_complaint" in note


def test_stub_can_force_failures():
    c = StubLLMClient(fail_times=2)
    with pytest.raises(LLMError):
        c.complete_json("p", SCHEMA)
    with pytest.raises(LLMError):
        c.complete_json("p", SCHEMA)
    note = c.complete_json("p", SCHEMA)  # 3rd call succeeds
    assert "chief_complaint" in note
    assert c.calls == 3


def test_registry_builds_stub(tmp_path):
    from medicscribe_server.llm_client.registry import build_llm_client
    cfg = tmp_path / "note.yaml"
    cfg.write_text("engine: stub\nmodel_id: x\n")
    client = build_llm_client(cfg)
    assert client.complete_json("p", {"type": "object"}).get("chief_complaint")


def test_registry_builds_openai_compat(tmp_path):
    from medicscribe_server.llm_client.registry import build_llm_client
    from medicscribe_server.llm_client.openai_compat import OpenAICompatClient
    cfg = tmp_path / "note.yaml"
    cfg.write_text(
        "engine: vllm\nmodel_id: qwen\nendpoint: http://localhost:8000/v1\n"
        "timeout_seconds: 60\nparams:\n  temperature: 0.2\n"
    )
    client = build_llm_client(cfg)
    assert isinstance(client, OpenAICompatClient)


def test_registry_rejects_unknown_engine(tmp_path):
    import pytest
    from medicscribe_server.llm_client.registry import build_llm_client
    cfg = tmp_path / "note.yaml"
    cfg.write_text("engine: banana\nmodel_id: x\n")
    with pytest.raises(ValueError):
        build_llm_client(cfg)
