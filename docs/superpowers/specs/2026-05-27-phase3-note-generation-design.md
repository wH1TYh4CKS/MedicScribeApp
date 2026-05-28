# Phase 3 — Note Generation Design

**Date:** 2026-05-27
**Status:** Approved for planning
**Depends on:** Phase 2 live ASR (merged). ASR config locked: `large-v3` + `task=translate` → English transcript.

## Product framing (drives every decision)

MedicScribe is a **doctor support tool, not a replacement**. The server is a **stateless transform**: audio → structured English note → return → done. The doctor verifies, edits, and exports the note into their own system. We bind nothing to a patient identity.

- **No PHI persistence.** No patient name, no appointment/visit binding, no transcript or note saved server-side. Audio exists only transiently during one recording and is deleted at Stop.
- **Accuracy bar ~80%+ is acceptable** — the value is freeing a doctor to converse with the patient instead of note-taking, especially for high-volume clinics (40–50 patients/day) and end-of-day fatigue where details get missed.
- **Doctor is always in the loop** — the note is a draft to verify/edit, never an authoritative record.

## Goals

1. On Stop, turn the accumulated English transcript into a structured SOAP note (`soap_v1` schema) and return it to the tablet (`note_done`).
2. **Delete the WAV at Stop** (right after final transcription), before note-gen. Note-gen never needs audio.
3. Build and test the full pipeline **without a running vLLM**, using a stub LLM client. Real vLLM (Qwen2.5-14B-AWQ) wiring is a deferred follow-up.
4. Guarantee no recording outlives its consult (reaper for crash-orphaned WAVs).

## Non-goals (v1)

- Diarization / speaker labels (flat transcript, `speaker=null`).
- Server-side persistence/export of notes (client owns export).
- Patient identity, EMR integration, appointment linkage.
- Real-model note-quality validation and ≤30s latency tuning (deferred to vLLM-wiring phase).
- A note-regeneration *endpoint* (retry is in-process only).

## Architecture

Mirrors the existing ASR adapter pattern (engine ABC + yaml registry).

```
                          ws/session.py (WSSession)
   PCM ─▶ Endpointer(VAD) ─▶ ASR ─▶ TranscriptFinal ─┐ (accumulate text)
                                                     │
   Stop ─▶ flush tail ─▶ delete WAV ─▶ NoteGenerator ─▶ note_done / error
                                          │
                          notes/template.py (render prompt.jinja + schema)
                                          │
                          llm_client/  base.LLMClient (ABC)
                                       ├─ openai_compat.py  (vLLM /v1, guided_json)  [deferred wiring]
                                       └─ stub.py           (canned valid SOAP)      [now]
                          registry.build_llm_client(note_llm.yaml)

   main.py lifespan: startup WAV reaper (TTL sweep) + build NoteGenerator
```

## Components

### `llm_client/` — transport
- **`base.py`** — `class LLMClient(ABC)`: `async def complete_json(self, system: str, user: str, schema: dict, params: dict) -> dict`. System/user split (not one blob) so OpenAI-style messages are clean.
- **`openai_compat.py`** — `OpenAICompatClient(LLMClient)`. httpx async POST to `{endpoint}/chat/completions`; model/params/timeout from `note_llm.yaml`; passes `extra_body={"guided_json": schema}` when `guided_decoding.enabled`. Raises on HTTP/timeout/non-JSON. **Coded now, exercised against real vLLM later.**
- **`stub.py`** — `StubLLMClient(LLMClient)`: returns a fixed schema-valid SOAP dict (and a mode that raises, for failure-path tests). Lets the pipeline run with no vLLM.
- **`registry.py`** — `build_llm_client(config_path) -> LLMClient`: `engine` `vllm`/`openai-compat` → OpenAICompat; `stub` → Stub. `note_llm.yaml` gets `engine: stub` for now.

### `notes/` — orchestration
- **`template.py`** — `NoteTemplate.load(name="soap_v1")`: reads `templates/<name>/prompt.jinja` + `output_schema.json` + shared parts (`prompts/system_doctor_scribe.jinja`, `prompts/style_guides/soap.md`, `prompts/few_shot/*.json`). `render(transcript) -> (system_text, user_text, schema)`.
- **`generator.py`** — `NoteGenerator(client, template)`. `async def generate(transcript: str) -> dict`: render → `complete_json` → validate vs schema (`jsonschema`) → return note dict. **Retries up to 3 times** on transport error or schema-validation failure; after 3 fails, raises `NoteGenerationError`. Optional progress callback for `note_progress` (coarse stages: `rendering`, `generating`, `validating`).

### `ws/session.py` — integration (surgical)
- Accumulate each emitted `TranscriptFinal.text` into `self.transcript_lines: list[str]`.
- `_on_stop`: flush tail → transcribe → close writer → **`wav_path.unlink(missing_ok=True)`** → if `note_generator` set and transcript non-empty: `note_progress` → `generate` → `note_done(note, raw_transcript)`. On `NoteGenerationError`: send `error("NOTE_FAILED", ...)`. Then phase=STOPPED.
- Raw transcript is still on the tablet from `transcript_final` lines, so a note failure degrades to "raw transcript only", not data loss.
- `_finalize` / disconnect path: also `wav_path.unlink(missing_ok=True)` — no WAV survives a session end.
- Inject `note_generator: NoteGenerator | None` like `asr`/`endpointer`.

### `store/` — recording reaper
- **`reaper.py`** — `purge_recordings(audio_dir, ttl_seconds)`: delete WAVs with mtime older than TTL. Called from `main.py` lifespan **on startup** (catches crash-orphaned WAVs). TTL configurable, default 3600s.

### Wiring & config
- `main.py` lifespan: run reaper, then build `NoteGenerator` from `note_llm.yaml` (if `note_enabled`).
- `config.py`: add `note_enabled: bool = True`, `note_config_path: Path = ../llm/models/note_llm.yaml`, `recording_ttl_seconds: int = 3600`.
- Router passes `note_generator` into `WSSession`.
- `note_llm.yaml`: set `engine: stub` for this phase (add `stub` to allowed engines).
- Phase 1/2 tests: set `note_enabled=false` (mirrors `asr_enabled` fixture) so Stop stays inert there.

### Dependencies (pyproject)
`httpx` (async LLM transport), `jinja2` (template render), `jsonschema` (note validation).

## Data flow on Stop
1. Flush VAD tail → final `transcript_final` sent.
2. Close + **delete WAV**.
3. If transcript empty → skip note, phase STOPPED (no error).
4. Else render prompt → `complete_json` (guided JSON) → validate. Retry ≤3.
5. Success → `note_done{note, raw_transcript}`. Failure after 3 → `error`. Phase STOPPED, ws closes.

## Data handling / PDPA
- Server is stateless: **nothing** (audio, transcript, note) persisted to disk; note returned over WS only.
- **No transcript/note content in logs** — logs carry only counts/durations/stages.
- WAV deleted at Stop and on any session-end path; reaper purges crash-orphans on startup.
- No patient identifiers collected or stored.

## Error handling
- LLM transport error / timeout / invalid-or-non-schema JSON → retry (≤3) → `NoteGenerationError` → `error("NOTE_FAILED")`. Tablet keeps raw transcript.
- Empty transcript → no note, no error.
- Reaper failures logged, non-fatal to boot.

## Testing (TDD)
- `StubLLMClient` (success) → `NoteGenerator.generate` returns schema-valid SOAP from a sample transcript.
- `StubLLMClient` (raising) → retries 3× then `NoteGenerationError`.
- Schema-invalid stub output → validation fails → retry → error.
- `NoteTemplate.load/render` → prompt contains transcript + schema; system/user split correct.
- Session: Stop with stub generator → `note_done` sent **and WAV deleted**; transcript accumulated correctly.
- Session: note failure → `error` sent, WAV already gone.
- Session: disconnect mid-recording → WAV deleted in finalize.
- Reaper: old WAV purged, fresh WAV kept.
- Don't mock ASR/LLM in integration beyond the injected stub seam (per CLAUDE.md).

## Deferred (next phase, documented)
- Stand up vLLM Qwen2.5-14B-AWQ; flip `note_llm.yaml engine: vllm`; validate guided_json on the nested SOAP schema (outlines can be slow on deep schemas).
- ≤30s latency budget validation with the real model.
- Real-device note-quality assessment on code-switched consults.
- Diarization (Phase 6) if multi-speaker note quality demands it.
