from pathlib import Path

from medicscribe_server.notes.template import NoteTemplate

LLM_ROOT = Path(__file__).resolve().parents[2] / "llm"


def test_load_and_render_soap_v1():
    tpl = NoteTemplate.load("soap_v1", LLM_ROOT)
    prompt, schema = tpl.render("Doctor: hello\nPatient: I have a fever")

    # schema is the SOAP JSON Schema
    assert isinstance(schema, dict)
    assert "chief_complaint" in schema["properties"]

    # the rendered prompt embeds the transcript, the schema, and the system rules
    assert "I have a fever" in prompt
    assert "chief_complaint" in prompt           # schema inlined
    assert "clinical scribe" in prompt.lower()   # system prompt inlined
    # few-shot examples rendered (example transcripts present)
    assert "Example 1" in prompt


def test_render_does_not_leak_schema_reference():
    """Mutating a returned schema must not corrupt later renders."""
    tpl = NoteTemplate.load("soap_v1", LLM_ROOT)
    _, schema1 = tpl.render("a")
    schema1["__poisoned__"] = True
    _, schema2 = tpl.render("b")
    assert "__poisoned__" not in schema2
