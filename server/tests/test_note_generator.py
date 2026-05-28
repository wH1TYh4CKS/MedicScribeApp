from pathlib import Path

import pytest

from medicscribe_server.llm_client.stub import StubLLMClient
from medicscribe_server.notes.generator import NoteGenerator, NoteGenerationError
from medicscribe_server.notes.template import NoteTemplate

LLM_ROOT = Path(__file__).resolve().parents[2] / "llm"


def _template():
    return NoteTemplate.load("soap_v1", LLM_ROOT)


def test_generate_returns_schema_valid_note():
    gen = NoteGenerator(StubLLMClient(), _template())
    note = gen.generate("Doctor: hi\nPatient: fever 2 days")
    assert note["chief_complaint"]
    assert isinstance(note["assessment"], list)


def test_retries_then_raises_after_three_failures():
    client = StubLLMClient(fail_times=99)
    gen = NoteGenerator(client, _template(), max_retries=3)
    with pytest.raises(NoteGenerationError):
        gen.generate("transcript")
    assert client.calls == 3


def test_retries_recover_before_limit():
    client = StubLLMClient(fail_times=2)  # 3rd call succeeds
    gen = NoteGenerator(client, _template(), max_retries=3)
    note = gen.generate("transcript")
    assert note["chief_complaint"]
    assert client.calls == 3


def test_schema_invalid_output_is_treated_as_failure():
    bad = StubLLMClient(response={"not_a_valid_field": 1})
    gen = NoteGenerator(bad, _template(), max_retries=3)
    with pytest.raises(NoteGenerationError):
        gen.generate("transcript")
    assert bad.calls == 3  # retried, never validated
