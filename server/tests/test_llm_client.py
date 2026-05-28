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
