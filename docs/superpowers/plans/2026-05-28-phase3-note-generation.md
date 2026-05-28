# Phase 3 Note Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** On Stop, turn the accumulated English transcript into a structured SOAP note and return it to the tablet; delete the WAV at Stop; purge crash-orphaned recordings on startup.

**Architecture:** Mirror the existing ASR adapter pattern (ABC + yaml registry). A **sync** `LLMClient` (Stub for now, OpenAI-compat vLLM coded for later) is wrapped in `asyncio.to_thread` in the WS session, exactly like the ASR engine. A `NoteTemplate` renders the existing `prompt.jinja` (which already bundles system prompt + style guide + few-shot + transcript) into one prompt string; `NoteGenerator` calls the client, validates against the SOAP schema, retries ≤3. Server persists nothing.

**Tech Stack:** Python 3.11, FastAPI, pydantic v2, Jinja2, jsonschema, httpx (sync). Tests: pytest + FastAPI `TestClient` (sync, no pytest_asyncio).

**Spec:** `docs/superpowers/specs/2026-05-27-phase3-note-generation-design.md`

**Note on a spec refinement:** The spec proposed an async `complete_json(system, user, schema, params)`. During planning we found (a) ASR is sync + `to_thread`-wrapped, and tests use sync `TestClient` with no async runner, and (b) `prompt.jinja` already bundles the system prompt into one complete prompt. So the client is **sync** with signature `complete_json(prompt: str, schema: dict) -> dict` (LLM params baked into the client at construction). Same behavior, better codebase fit.

---

## File Structure

- Create `server/src/medicscribe_server/llm_client/__init__.py` — package marker.
- Create `server/src/medicscribe_server/llm_client/base.py` — `LLMClient` ABC + `LLMError`.
- Create `server/src/medicscribe_server/llm_client/stub.py` — `StubLLMClient`.
- Create `server/src/medicscribe_server/llm_client/openai_compat.py` — `OpenAICompatClient` (vLLM, guided_json).
- Create `server/src/medicscribe_server/llm_client/registry.py` — `build_llm_client(config_path)`.
- Create `server/src/medicscribe_server/notes/__init__.py` — package marker.
- Create `server/src/medicscribe_server/notes/template.py` — `NoteTemplate` (load + render).
- Create `server/src/medicscribe_server/notes/generator.py` — `NoteGenerator` + `NoteGenerationError`.
- Create `server/src/medicscribe_server/store/reaper.py` — `purge_recordings`.
- Modify `server/src/medicscribe_server/config.py` — add note + reaper settings.
- Modify `server/src/medicscribe_server/ws/session.py` — accumulate transcript, delete WAV, generate note.
- Modify `server/src/medicscribe_server/ws/router.py` — inject `note_generator`.
- Modify `server/src/medicscribe_server/main.py` — reaper on startup + build `NoteGenerator`.
- Modify `server/pyproject.toml` — add `jsonschema` to deps.
- Modify `llm/models/note_llm.yaml` — `engine: stub` for this phase.
- Tests: `test_llm_client.py`, `test_note_template.py`, `test_note_generator.py`, `test_openai_compat.py`, `test_reaper.py`, `test_ws_note.py`.

All commands run from `server/`. Interpreter: `.venv/bin/python`, `.venv/bin/pytest`.

---

### Task 1: Dependencies + settings

**Files:**
- Modify: `server/pyproject.toml`
- Modify: `server/src/medicscribe_server/config.py`

- [ ] **Step 1: Add `jsonschema` to dependencies**

In `server/pyproject.toml`, add to the `dependencies` list (after `"requests~=2.32",`):
```toml
    "jinja2~=3.1",
    "jsonschema~=4.23",
```
(`httpx` is already in the `dev`/optional deps and present in the venv; `jinja2` is present transitively — pin it explicitly here since we now import it directly.)

- [ ] **Step 2: Install**

Run: `.venv/bin/pip install jsonschema "jinja2~=3.1"`
Expected: installs jsonschema; jinja2 already satisfied.

- [ ] **Step 3: Add settings**

In `server/src/medicscribe_server/config.py`, add inside `Settings` after the ASR fields:
```python
    # Note generation
    note_enabled: bool = True
    note_config_path: Path = Path("../llm/models/note_llm.yaml")
    note_template: str = "soap_v1"
    llm_root: Path = Path("../llm")

    # Recording retention (PDPA): purge WAVs older than this on startup.
    recording_ttl_seconds: int = 3600
```

- [ ] **Step 4: Verify import**

Run: `PYTHONPATH=src .venv/bin/python -c "from medicscribe_server.config import settings; print(settings.note_enabled, settings.recording_ttl_seconds)"`
Expected: `True 3600`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/medicscribe_server/config.py
git commit -m "feat: add jsonschema dep + note-gen settings"
```

---

### Task 2: LLMClient ABC + StubLLMClient

**Files:**
- Create: `server/src/medicscribe_server/llm_client/__init__.py`
- Create: `server/src/medicscribe_server/llm_client/base.py`
- Create: `server/src/medicscribe_server/llm_client/stub.py`
- Test: `server/tests/test_llm_client.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_llm_client.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm_client.py -v`
Expected: FAIL — `ModuleNotFoundError: medicscribe_server.llm_client`

- [ ] **Step 3: Write minimal implementation**

Create `server/src/medicscribe_server/llm_client/__init__.py`:
```python
```
(empty file)

Create `server/src/medicscribe_server/llm_client/base.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Transport/protocol failure talking to the note-generation LLM."""


class LLMClient(ABC):
    """Sync LLM transport. Wrapped in asyncio.to_thread by the WS session."""

    @abstractmethod
    def complete_json(self, prompt: str, schema: dict) -> dict:
        """Send `prompt`, return a parsed JSON object constrained to `schema`.

        Raises LLMError on transport failure or unparseable output.
        """
        raise NotImplementedError
```

Create `server/src/medicscribe_server/llm_client/stub.py`:
```python
from __future__ import annotations

from medicscribe_server.llm_client.base import LLMClient, LLMError

_DEFAULT_NOTE = {
    "chief_complaint": "Headache since this morning.",
    "subjective": {"history_of_present_illness": "Patient reports headache since morning, no trauma."},
    "objective": {},
    "assessment": [{"problem": "Tension headache"}],
    "plan": [{"action": "Paracetamol 500mg PRN; review if persists."}],
    "medications": [{"name": "Paracetamol", "dose": "500mg", "frequency": "PRN"}],
    "allergies": [],
    "follow_up": "Return if symptoms worsen.",
}


class StubLLMClient(LLMClient):
    """In-memory client for tests and pipeline dev without a running vLLM.

    `fail_times` makes the first N calls raise LLMError (to exercise retries).
    """

    def __init__(self, response: dict | None = None, fail_times: int = 0) -> None:
        self._response = response if response is not None else _DEFAULT_NOTE
        self._fail_times = fail_times
        self.calls = 0

    def complete_json(self, prompt: str, schema: dict) -> dict:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise LLMError(f"stub forced failure {self.calls}")
        return self._response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm_client.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/medicscribe_server/llm_client/ tests/test_llm_client.py
git commit -m "feat: LLMClient ABC + stub client"
```

---

### Task 3: OpenAICompatClient (vLLM transport)

**Files:**
- Create: `server/src/medicscribe_server/llm_client/openai_compat.py`
- Test: `server/tests/test_openai_compat.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_openai_compat.py`:
```python
import json

import httpx
import pytest

from medicscribe_server.llm_client.base import LLMError
from medicscribe_server.llm_client.openai_compat import OpenAICompatClient

SCHEMA = {"type": "object", "required": ["chief_complaint"],
          "properties": {"chief_complaint": {"type": "string"}}}


def _client(handler):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="http://test")
    return OpenAICompatClient(
        endpoint="http://test/v1", model="qwen", params={"temperature": 0.2, "max_tokens": 800},
        timeout=10, guided=True, http_client=http,
    )


def test_builds_request_and_parses_content():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        content = json.dumps({"chief_complaint": "Fever for 2 days."})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    note = _client(handler).complete_json("the prompt", SCHEMA)
    assert note == {"chief_complaint": "Fever for 2 days."}
    assert seen["url"].endswith("/v1/chat/completions")
    assert seen["body"]["model"] == "qwen"
    assert seen["body"]["messages"][0]["role"] == "user"
    assert seen["body"]["messages"][0]["content"] == "the prompt"
    assert seen["body"]["guided_json"] == SCHEMA
    assert seen["body"]["temperature"] == 0.2


def test_http_error_raises_llmerror():
    def handler(request):
        return httpx.Response(500, text="boom")
    with pytest.raises(LLMError):
        _client(handler).complete_json("p", SCHEMA)


def test_non_json_content_raises_llmerror():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
    with pytest.raises(LLMError):
        _client(handler).complete_json("p", SCHEMA)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_openai_compat.py -v`
Expected: FAIL — `ModuleNotFoundError: ...openai_compat`

- [ ] **Step 3: Write minimal implementation**

Create `server/src/medicscribe_server/llm_client/openai_compat.py`:
```python
from __future__ import annotations

import json

import httpx

from medicscribe_server.llm_client.base import LLMClient, LLMError


class OpenAICompatClient(LLMClient):
    """Talks to an OpenAI-compatible server (vLLM serving Qwen2.5-14B-AWQ).

    Uses vLLM's `guided_json` extension for schema-constrained output.
    Coded now; exercised against a real vLLM in a later phase.
    """

    def __init__(
        self,
        endpoint: str,
        model: str,
        params: dict,
        timeout: float = 60.0,
        api_key: str | None = None,
        guided: bool = True,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._params = params or {}
        self._guided = guided
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = http_client or httpx.Client(timeout=timeout, headers=headers)

    def complete_json(self, prompt: str, schema: dict) -> dict:
        body: dict = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._params.get("temperature", 0.2),
            "top_p": self._params.get("top_p", 0.9),
            "max_tokens": self._params.get("max_tokens", 800),
        }
        if self._guided:
            body["guided_json"] = schema
        try:
            resp = self._http.post(f"{self._endpoint}/chat/completions", json=body)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM returned non-JSON content: {exc}") from exc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_openai_compat.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/medicscribe_server/llm_client/openai_compat.py tests/test_openai_compat.py
git commit -m "feat: OpenAI-compat vLLM client with guided_json"
```

---

### Task 4: NoteTemplate loader

**Files:**
- Create: `server/src/medicscribe_server/notes/__init__.py`
- Create: `server/src/medicscribe_server/notes/template.py`
- Test: `server/tests/test_note_template.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_note_template.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_note_template.py -v`
Expected: FAIL — `ModuleNotFoundError: ...notes.template`

- [ ] **Step 3: Write minimal implementation**

Create `server/src/medicscribe_server/notes/__init__.py`:
```python
```
(empty file)

Create `server/src/medicscribe_server/notes/template.py`:
```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import jinja2


@dataclass
class NoteTemplate:
    """A note template = a Jinja prompt + a JSON Schema + shared prompt parts.

    Layout under `llm_root`:
      templates/<name>/prompt.jinja
      templates/<name>/output_schema.json
      prompts/system_doctor_scribe.jinja
      prompts/style_guides/soap.md
      prompts/few_shot/*.json   (each: {"transcript": str, "note_json": obj|str})
    """

    name: str
    schema: dict
    _prompt: jinja2.Template
    _system: str
    _style_guide: str
    _few_shot: list[dict]

    @classmethod
    def load(cls, name: str, llm_root: Path) -> "NoteTemplate":
        llm_root = Path(llm_root)
        tdir = llm_root / "templates" / name
        schema = json.loads((tdir / "output_schema.json").read_text(encoding="utf-8"))
        prompt = jinja2.Template((tdir / "prompt.jinja").read_text(encoding="utf-8"))
        system = (llm_root / "prompts" / "system_doctor_scribe.jinja").read_text(encoding="utf-8")
        style = (llm_root / "prompts" / "style_guides" / "soap.md").read_text(encoding="utf-8")

        few_shot: list[dict] = []
        fs_dir = llm_root / "prompts" / "few_shot"
        for fp in sorted(fs_dir.glob("*.json")):
            ex = json.loads(fp.read_text(encoding="utf-8"))
            note_json = ex.get("note_json", "")
            if not isinstance(note_json, str):
                note_json = json.dumps(note_json, ensure_ascii=False, indent=2)
            few_shot.append({"transcript": ex.get("transcript", ""), "note_json": note_json})

        return cls(name=name, schema=schema, _prompt=prompt, _system=system,
                   _style_guide=style, _few_shot=few_shot)

    def render(self, transcript: str) -> tuple[str, dict]:
        prompt = self._prompt.render(
            system_prompt=self._system,
            style_guide=self._style_guide,
            few_shot=self._few_shot,
            transcript=transcript,
            output_schema_json=json.dumps(self.schema, ensure_ascii=False, indent=2),
        )
        return prompt, self.schema
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_note_template.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/medicscribe_server/notes/__init__.py src/medicscribe_server/notes/template.py tests/test_note_template.py
git commit -m "feat: NoteTemplate loader + renderer"
```

---

### Task 5: NoteGenerator (retry + schema validation)

**Files:**
- Create: `server/src/medicscribe_server/notes/generator.py`
- Test: `server/tests/test_note_generator.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_note_generator.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_note_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: ...notes.generator`

- [ ] **Step 3: Write minimal implementation**

Create `server/src/medicscribe_server/notes/generator.py`:
```python
from __future__ import annotations

import logging

import jsonschema

from medicscribe_server.llm_client.base import LLMClient, LLMError
from medicscribe_server.notes.template import NoteTemplate

logger = logging.getLogger(__name__)


class NoteGenerationError(Exception):
    """Note generation failed after all retries."""


class NoteGenerator:
    """Render prompt -> call LLM -> validate against schema, with bounded retries.

    Sync (wrapped in asyncio.to_thread by the WS session). Never logs transcript
    or note content (PHI) — only attempt counts and error types.
    """

    def __init__(self, client: LLMClient, template: NoteTemplate, max_retries: int = 3) -> None:
        self._client = client
        self._template = template
        self._max_retries = max_retries

    def generate(self, transcript: str) -> dict:
        prompt, schema = self._template.render(transcript)
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                note = self._client.complete_json(prompt, schema)
                jsonschema.validate(note, schema)
                return note
            except (LLMError, jsonschema.ValidationError) as exc:
                last_error = exc
                logger.warning("note-gen attempt %d/%d failed: %s",
                               attempt, self._max_retries, type(exc).__name__)
        raise NoteGenerationError(
            f"note generation failed after {self._max_retries} attempts"
        ) from last_error
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_note_generator.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/medicscribe_server/notes/generator.py tests/test_note_generator.py
git commit -m "feat: NoteGenerator with retry + schema validation"
```

---

### Task 6: LLM client registry

**Files:**
- Create: `server/src/medicscribe_server/llm_client/registry.py`
- Modify: `llm/models/note_llm.yaml`
- Test: append to `server/tests/test_llm_client.py`

- [ ] **Step 1: Write the failing test**

Append to `server/tests/test_llm_client.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_llm_client.py -v`
Expected: FAIL — `ModuleNotFoundError: ...llm_client.registry`

- [ ] **Step 3: Write minimal implementation**

Create `server/src/medicscribe_server/llm_client/registry.py`:
```python
from __future__ import annotations

from pathlib import Path

import yaml

from medicscribe_server.llm_client.base import LLMClient
from medicscribe_server.llm_client.openai_compat import OpenAICompatClient
from medicscribe_server.llm_client.stub import StubLLMClient


def load_note_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_llm_client(config_path: Path) -> LLMClient:
    cfg = load_note_config(config_path)
    engine = cfg.get("engine")
    if engine == "stub":
        return StubLLMClient()
    if engine in ("vllm", "openai-compat", "tgi"):
        return OpenAICompatClient(
            endpoint=cfg["endpoint"],
            model=cfg["model_id"],
            params=cfg.get("params", {}),
            timeout=float(cfg.get("timeout_seconds", 60)),
            api_key=cfg.get("api_key"),
            guided=bool(cfg.get("guided_decoding", {}).get("enabled", True)),
        )
    raise ValueError(f"unknown note-gen engine: {engine}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_llm_client.py -v`
Expected: PASS (5 tests total)

- [ ] **Step 5: Switch note_llm.yaml to stub for this phase**

In `llm/models/note_llm.yaml`, change the engine line:
```yaml
engine: stub                  # was: vllm. Phase 3 builds against stub; flip to vllm when Qwen is served.
```
Leave all other fields (model_id, endpoint, params, guided_decoding) intact for the vLLM-wiring phase.

- [ ] **Step 6: Commit**

```bash
git add src/medicscribe_server/llm_client/registry.py tests/test_llm_client.py ../llm/models/note_llm.yaml
git commit -m "feat: note LLM client registry; default to stub engine"
```

---

### Task 7: Recording reaper

**Files:**
- Create: `server/src/medicscribe_server/store/reaper.py`
- Test: `server/tests/test_reaper.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_reaper.py`:
```python
import os
import time

from medicscribe_server.store.reaper import purge_recordings


def test_purges_old_wavs_keeps_fresh(tmp_path):
    old = tmp_path / "old.wav"
    fresh = tmp_path / "fresh.wav"
    old.write_bytes(b"RIFF")
    fresh.write_bytes(b"RIFF")
    # backdate `old` by 2 hours
    two_hours = time.time() - 7200
    os.utime(old, (two_hours, two_hours))

    removed = purge_recordings(tmp_path, ttl_seconds=3600)

    assert old.name in [p.name for p in removed]
    assert not old.exists()
    assert fresh.exists()


def test_missing_dir_is_noop(tmp_path):
    assert purge_recordings(tmp_path / "nope", ttl_seconds=3600) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_reaper.py -v`
Expected: FAIL — `ModuleNotFoundError: ...store.reaper`

- [ ] **Step 3: Write minimal implementation**

Create `server/src/medicscribe_server/store/reaper.py`:
```python
from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def purge_recordings(audio_dir: Path, ttl_seconds: int) -> list[Path]:
    """Delete *.wav older than ttl_seconds. PDPA: no recording outlives its consult.

    Returns the list of removed paths. Missing dir or unlink errors are non-fatal.
    """
    audio_dir = Path(audio_dir)
    if not audio_dir.is_dir():
        return []
    cutoff = time.time() - ttl_seconds
    removed: list[Path] = []
    for wav in audio_dir.glob("*.wav"):
        try:
            if wav.stat().st_mtime < cutoff:
                wav.unlink()
                removed.append(wav)
        except OSError:
            logger.warning("reaper could not remove %s", wav.name)
    if removed:
        logger.info("reaper purged %d stale recording(s)", len(removed))
    return removed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_reaper.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/medicscribe_server/store/reaper.py tests/test_reaper.py
git commit -m "feat: recording reaper (startup TTL purge)"
```

---

### Task 8: Session integration — accumulate transcript, delete WAV, generate note

**Files:**
- Modify: `server/src/medicscribe_server/ws/session.py`
- Test: `server/tests/test_ws_note.py`

- [ ] **Step 1: Write the failing test**

Create `server/tests/test_ws_note.py`:
```python
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


class StubEndpointer:
    def __init__(self, threshold_bytes=16000):
        self._threshold = threshold_bytes
        self._buf = bytearray()
        self._ready = []

    def accept(self, frame):
        self._buf.extend(frame)
        if len(self._buf) >= self._threshold:
            self._ready.append(bytes(self._buf))
            self._buf = bytearray()

    def pop_utterance(self):
        return self._ready.pop(0) if self._ready else None

    def flush(self):
        tail = bytes(self._buf) if self._buf else None
        self._buf = bytearray()
        return tail


class StubNoteGen:
    def __init__(self, fail=False):
        self.fail = fail
        self.seen_transcript = None

    def generate(self, transcript):
        from medicscribe_server.notes.generator import NoteGenerationError
        self.seen_transcript = transcript
        if self.fail:
            raise NoteGenerationError("boom")
        return {"chief_complaint": "Fever", "subjective": {"history_of_present_illness": "fever"},
                "assessment": [{"problem": "Viral fever"}], "plan": [{"action": "rest"}]}


def _pcm(seconds, sr=16000):
    n = int(seconds * sr)
    return struct.pack("<" + "h" * n, *[int(20000 * math.sin(i / 5)) for i in range(n)])


def _make_client(tmp_path, monkeypatch, note_gen):
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()
    monkeypatch.setattr(settings, "audio_dir", audio_dir)
    app = FastAPI()
    app.state.asr_engine = StubASR()
    app.state.make_endpointer = lambda: StubEndpointer()
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
    assert done[0]["note"]["chief_complaint"] == "Fever"
    assert "I have a fever" in done[0]["raw_transcript"]
    assert "I have a fever" in gen.seen_transcript
    # PDPA: WAV deleted at stop
    assert list(audio_dir.glob("*.wav")) == []


def test_note_failure_sends_error_and_wav_still_deleted(tmp_path, monkeypatch):
    client, audio_dir = _make_client(tmp_path, monkeypatch, StubNoteGen(fail=True))
    messages = _run_session(client, "s-note-2")
    assert any(m["type"] == "error" and m["code"] == "NOTE_FAILED" for m in messages)
    assert list(audio_dir.glob("*.wav")) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_ws_note.py -v`
Expected: FAIL — no `note_done` (session doesn't generate notes yet)

- [ ] **Step 3: Modify the session**

In `server/src/medicscribe_server/ws/session.py`:

(a) Add `NoteDone`, `NoteProgress` to the protocol import block:
```python
from medicscribe_server.ws.protocol import (
    AckMessage,
    ClientMessage,
    ErrorMessage,
    NoteDone,
    NoteProgress,
    StartMessage,
    StopMessage,
    TranscriptFinal,
)
```

(b) Extend `__init__` signature and add new attributes. Replace the `__init__` signature line and body additions:
```python
    def __init__(
        self,
        ws: WebSocket,
        audio_dir: Path,
        sample_rate: int = 16000,
        asr: ASREngine | None = None,
        endpointer: Endpointer | None = None,
        note_generator: "NoteGenerator | None" = None,
    ) -> None:
        self.ws = ws
        self.audio_dir = audio_dir
        self.sample_rate = sample_rate
        self.asr = asr
        self.endpointer = endpointer
        self.note_generator = note_generator
        self.phase: SessionPhase = SessionPhase.INIT
        self.writer: WavWriter | None = None
        self.session_id: str | None = None
        self.wav_path: Path | None = None
        self.transcript_lines: list[str] = []
        self.bytes_written = 0
        # Serialize whisper calls — the engine is not safe under concurrent use.
        self._asr_lock = asyncio.Lock()
```

(c) Add the TYPE_CHECKING import for `NoteGenerator` (in the existing `if TYPE_CHECKING:` block):
```python
if TYPE_CHECKING:
    from medicscribe_server.asr.base import ASREngine
    from medicscribe_server.asr.vad import Endpointer
    from medicscribe_server.notes.generator import NoteGenerator
```

(d) In `_on_start`, record `self.wav_path`. Replace the two lines that build `wav_path`/writer:
```python
        self.wav_path = self.audio_dir / f"{self.session_id}.wav"
        self.writer = WavWriter(self.wav_path, sample_rate=self.sample_rate)
```

(e) In `_transcribe_and_send`, accumulate transcript text. Replace the send loop:
```python
        for seg in segments:
            self.transcript_lines.append(seg.text)
            await self._send(
                TranscriptFinal(text=seg.text, lang=seg.lang, t=seg.t0)
            )
```

(f) Replace `_on_stop` entirely with:
```python
    async def _on_stop(self) -> None:
        if self._transcribing and self.endpointer is not None:
            tail = self.endpointer.flush()
            if tail:
                await self._transcribe_and_send(tail)
        if self.writer is not None:
            duration = self.writer.duration_seconds()
            self.writer.close()
            self.writer = None
            logger.info(
                "Session %s stopped. bytes=%d duration=%.2fs",
                self.session_id, self.bytes_written, duration,
            )
        # PDPA: note-gen uses the transcript text, not the audio. Delete the WAV now.
        self._delete_wav()
        await self._maybe_generate_note()
        self.phase = SessionPhase.STOPPED

    def _delete_wav(self) -> None:
        if self.wav_path is not None:
            try:
                self.wav_path.unlink(missing_ok=True)
            except OSError:
                logger.warning("could not delete wav for session %s", self.session_id)
            self.wav_path = None

    async def _maybe_generate_note(self) -> None:
        transcript = "\n".join(self.transcript_lines).strip()
        if self.note_generator is None or not transcript:
            return
        await self._send(NoteProgress(stage="generating", pct=50))
        try:
            note = await asyncio.to_thread(self.note_generator.generate, transcript)
        except Exception as exc:  # NoteGenerationError and anything unexpected
            logger.warning("note generation failed for session %s: %s",
                           self.session_id, type(exc).__name__)
            await self._send_error("NOTE_FAILED", "Note generation failed")
            return
        await self._send(NoteDone(note=note, raw_transcript=transcript))
```

(g) Update `_finalize` to also delete the WAV (covers disconnect/crash-with-open-session):
```python
    def _finalize(self) -> None:
        if self.writer is not None:
            try:
                self.writer.close()
            except Exception:
                logger.exception("Failed to close writer in finalize")
            self.writer = None
        self._delete_wav()
```

Note: `_send_error` sets `phase = ERROR`; `_on_stop` sets `STOPPED` afterward. That is fine — both end the run loop. Leave `_send_error` as-is.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_ws_note.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the existing WS/transcribe tests for regression**

Run: `.venv/bin/pytest tests/test_ws_transcribes.py tests/test_ws_session.py -v`
Expected: PASS (those build their app without `note_generator`; `getattr` defaults it to None, so Stop stays inert there)

- [ ] **Step 6: Commit**

```bash
git add src/medicscribe_server/ws/session.py tests/test_ws_note.py
git commit -m "feat: generate note on stop, delete WAV (PDPA)"
```

---

### Task 9: Wire reaper + note generator into app

**Files:**
- Modify: `server/src/medicscribe_server/main.py`
- Modify: `server/src/medicscribe_server/ws/router.py`

- [ ] **Step 1: Inject note_generator in the router**

In `server/src/medicscribe_server/ws/router.py`, replace the body of `scribe_ws` after `await ws.accept()`:
```python
    asr = getattr(ws.app.state, "asr_engine", None)
    make_endpointer = getattr(ws.app.state, "make_endpointer", None)
    note_generator = getattr(ws.app.state, "note_generator", None)
    session = WSSession(
        ws=ws,
        audio_dir=settings.audio_dir,
        sample_rate=settings.audio_sample_rate,
        asr=asr,
        endpointer=make_endpointer() if (asr and make_endpointer) else None,
        note_generator=note_generator,
    )
    await session.run()
```

- [ ] **Step 2: Reaper + note generator in lifespan**

In `server/src/medicscribe_server/main.py`, replace the `lifespan` function body before `try: yield` (keep the ASR block, add reaper at the very start and a note block after ASR):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from medicscribe_server.store.reaper import purge_recordings

    purge_recordings(settings.audio_dir, settings.recording_ttl_seconds)

    app.state.asr_engine = None
    app.state.make_endpointer = None
    if settings.asr_enabled:
        from medicscribe_server.asr.registry import build_asr, build_endpointer

        logger.info("Loading ASR model from %s ...", settings.asr_config_path)
        app.state.asr_engine = build_asr(settings.asr_config_path)
        app.state.make_endpointer = lambda: build_endpointer(settings.asr_config_path)
        logger.info("ASR model ready")
    else:
        logger.info("ASR disabled (MEDICSCRIBE_ASR_ENABLED=false) — WAV-only mode")

    app.state.note_generator = None
    if settings.note_enabled:
        from medicscribe_server.llm_client.registry import build_llm_client
        from medicscribe_server.notes.generator import NoteGenerator
        from medicscribe_server.notes.template import NoteTemplate

        client = build_llm_client(settings.note_config_path)
        template = NoteTemplate.load(settings.note_template, settings.llm_root)
        app.state.note_generator = NoteGenerator(client, template)
        logger.info("Note generator ready (engine from %s)", settings.note_config_path)
    else:
        logger.info("Note generation disabled (MEDICSCRIBE_NOTE_ENABLED=false)")

    try:
        yield
    finally:
        if app.state.asr_engine is not None:
            app.state.asr_engine.close()
```

- [ ] **Step 3: Verify the app boots with the stub engine (no vLLM needed)**

Run:
```bash
PYTHONPATH=src .venv/bin/python -c "
from medicscribe_server.main import create_app
import asyncio
app = create_app()
async def boot():
    async with app.router.lifespan_context(app):
        print('note_generator:', type(app.state.note_generator).__name__)
        print('asr_engine:', app.state.asr_engine)
asyncio.run(boot())
" 2>&1 | grep -viE 'warning'
```
Expected: prints `note_generator: NoteGenerator` (ASR may load the real model — set `MEDICSCRIBE_ASR_ENABLED=false` to skip: prepend it to the command).

- [ ] **Step 4: Full fast test suite**

Run: `.venv/bin/pytest -m "not slow" -v`
Expected: PASS (all fast tests, including new note tests + existing WS tests)

- [ ] **Step 5: Commit**

```bash
git add src/medicscribe_server/main.py src/medicscribe_server/ws/router.py
git commit -m "feat: wire reaper + note generator into app lifespan"
```

---

### Task 10: End-to-end smoke (stub) + docs

**Files:**
- Modify: `docs/superpowers/specs/2026-05-27-phase3-note-generation-design.md` (mark phase status)
- (No new code)

- [ ] **Step 1: Manual E2E with the running server + stub engine**

Boot the server (background, per ops note — run_in_background only), then drive the WS with a short PCM and confirm a `note_done` arrives and no WAV remains. With `engine: stub`, the note is the canned stub note — this validates the **plumbing end to end**, not note quality.

Run (boots, sends 1s tone, prints message types, checks audio dir):
```bash
PYTHONPATH=src MEDICSCRIBE_ASR_ENABLED=true .venv/bin/python - <<'PY'
# Uses TestClient against the real create_app() lifespan (stub note engine).
import json, math, struct
from fastapi.testclient import TestClient
from medicscribe_server.main import create_app
app = create_app()
with TestClient(app) as client:
    pcm = struct.pack("<"+"h"*16000, *[int(15000*math.sin(i/5)) for i in range(16000)])
    with client.websocket_connect("/ws/scribe") as ws:
        ws.send_text(json.dumps({"type":"start","session_id":"smoke-1"}))
        ws.receive_text()
        for i in range(0,len(pcm),640): ws.send_bytes(pcm[i:i+640])
        ws.send_text(json.dumps({"type":"stop"}))
        types=[]
        for _ in range(80):
            try: types.append(json.loads(ws.receive_text())["type"])
            except Exception: break
    print("message types:", types)
PY
```
Expected: types include `ack` and `note_done` (real whisper may emit 0 transcripts for a pure tone → then `note_done` is skipped; if so, re-run logic is fine — the unit tests already prove note-gen). Document whichever occurs.

- [ ] **Step 2: Update spec status**

In `docs/superpowers/specs/2026-05-27-phase3-note-generation-design.md`, change the `**Status:**` line to:
```markdown
**Status:** Implemented (stub LLM). vLLM Qwen wiring + latency/quality validation deferred.
```

- [ ] **Step 3: Commit**

```bash
git add docs/superpowers/specs/2026-05-27-phase3-note-generation-design.md
git commit -m "docs: mark phase 3 note-gen implemented (stub)"
```

---

## Self-Review

**Spec coverage:**
- Note-gen on Stop → Tasks 4,5,8. ✓
- Delete WAV at Stop + every session-end → Task 8 (`_on_stop`, `_finalize`). ✓
- Build/test without vLLM (stub) → Tasks 2,6 (`engine: stub`). ✓
- Reaper for orphans → Task 7 + wired Task 9. ✓
- Retry ×3 → Task 5. ✓
- Stateless / no PHI in logs → generator + session log only counts/types. ✓
- OpenAI-compat client coded for later → Task 3. ✓
- `note_enabled` gating, existing tests inert → Task 1 + Task 8 step 5 + Task 9. ✓
- Deps (jsonschema/jinja2/httpx) → Task 1. ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. ✓

**Type consistency:** `complete_json(prompt, schema)` consistent across base/stub/openai_compat/generator. `NoteGenerator(client, template, max_retries)` consistent in tests + wiring. `NoteTemplate.load(name, llm_root)` / `render(transcript) -> (prompt, schema)` consistent. `purge_recordings(audio_dir, ttl_seconds)` consistent. `WSSession(..., note_generator=None)` consistent in router + tests. ✓

**Deviation logged:** sync client (not async) + single prompt (not system/user split) — documented in header, matches ASR pattern + existing `prompt.jinja`.
