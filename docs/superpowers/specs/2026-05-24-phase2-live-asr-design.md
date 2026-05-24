# Phase 2 — Live ASR (server-side streaming transcription)

**Date:** 2026-05-24
**Status:** Approved, building
**Depends on:** Phase 1 (audio capture → WS → WAV), complete.

## Goal

Streamed consultation audio is transcribed on the server and the recognized
text is pushed back to the tablet in near-real-time. The doctor sees words land
on screen as the consultation proceeds. Code-switched Manglish (EN/ZH/MS/TA) is
auto-detected per utterance — no forced language.

This is the first half of the test loop the user asked for:

```
phone mic → stream PCM → server (silero-VAD + whisper-large-v3) → transcript on phone
```

Phase 3 (note generation with Qwen-14B) is a separate spec and consumes the
final transcript produced here.

## Scope decision

- **Approach B — VAD-segmented, final-only.** silero-VAD detects speech/silence
  boundaries on the live frame stream. When an utterance ends (silence exceeds
  threshold), the buffered utterance PCM is transcribed once with
  whisper-large-v3 and emitted as `transcript_final`.
- `transcript_partial` (live within-utterance streaming, approach A) is **out of
  scope** for Phase 2. The protocol field already exists, so it can be added
  later with no rework.
- ASR runs **server-side**. Phone stays a thin client (mic + display).
- Both ASR (~6 GB) loads at server boot. Qwen note LLM is NOT loaded in Phase 2.

## Architecture

New package `server/src/medicscribe_server/asr/`:

| File | Responsibility | Depends on |
|---|---|---|
| `base.py` | `ASREngine` ABC + `Segment` dataclass. Contract: `transcribe(pcm: bytes, sample_rate: int) -> list[Segment]`. | — |
| `faster_whisper_engine.py` | Concrete engine wrapping `faster_whisper.WhisperModel`. Converts 16-bit PCM → float32 ndarray, calls `transcribe(language=None, vad_filter=True, ...)`, maps to `Segment`. | faster-whisper, numpy |
| `vad.py` | `Endpointer` — wraps silero-VAD `VADIterator`. Accepts 20 ms PCM frames, rebuffers to 512-sample (32 ms @16k) windows silero requires, emits the completed utterance PCM when trailing silence ≥ `min_silence_ms`. | silero-vad, torch |
| `registry.py` | Reads `llm/models/asr.yaml`, validates schema, constructs the configured engine + endpointer. Single source of model identity. | pyyaml |
| `__init__.py` | Re-exports `ASREngine`, `Segment`, `build_asr`, `Endpointer`. | — |

`Segment` fields: `text: str`, `lang: str | None`, `t0: float`, `t1: float`.

### Data flow

```
PCM 20ms frame (640B) ──▶ WSSession._on_pcm
                            ├─ writer.write(frame)            # Phase 1, kept for debug
                            └─ endpointer.accept(frame)
                                  └─ on utterance-end:
                                       utterance_pcm = endpointer.flush()
                                       segs = asr.transcribe(utterance_pcm, sr)
                                       for s in segs:
                                           send TranscriptFinal(text=s.text, lang=s.lang, t=s.t0)
On Stop ──▶ WSSession._on_stop
              ├─ tail = endpointer.flush()                    # drain pending speech
              ├─ if tail: transcribe + emit final
              └─ close writer
```

Transcription runs in a worker thread (`asyncio.to_thread`) so the event loop is
not blocked while whisper decodes.

### Lifecycle / wiring

- `main.py` gains a FastAPI `lifespan` that calls `build_asr()` once at startup
  and stores the engine + an endpointer factory on `app.state`. Shutdown disposes
  the model.
- `ws/router.py` reads the engine from `app.state` and passes it into `WSSession`.
- `WSSession.__init__` accepts an optional `asr: ASREngine | None`. When `None`
  (unit tests, Phase 1 mode) it behaves exactly as today — WAV only, no
  transcription. This keeps Phase 1 tests green and makes ASR injectable.

### Config

`asr.yaml` already defines engine/model/params/vad — honored as-is. `config.py`
gains one field: `asr_config_path: Path = Path("../llm/models/asr.yaml")`
(resolved relative to repo root; overridable via `MEDICSCRIBE_ASR_CONFIG_PATH`).
A `MEDICSCRIBE_ASR_ENABLED: bool = True` flag lets tests/dev boot the server
without loading the 6 GB model.

### Protocol changes

`ws/protocol.py`: add `lang: str | None = None` to both `TranscriptPartial` and
`TranscriptFinal`. Mirror in Android `net/Protocol.kt` (`@SerialName("lang")`,
nullable). Backward compatible — field is optional.

### Phone changes

`RecordScreen.kt` / `RecordController`:
- Collect `ServerMessage.TranscriptFinal` events → append `text` to a
  `transcript: List<String>` in `SessionState`.
- UI: scrollable transcript box (LazyColumn) above the Record/Stop button. Each
  final segment is one line, optionally prefixed with detected `lang`.
- No new permissions, no new deps.

## Dependencies

Add to `server/pyproject.toml` `dependencies`:
- `faster-whisper~=1.0.3`
- `ctranslate2~=4.4`
- `silero-vad~=5.1`
- `numpy~=2.0`

torch is pulled transitively by silero-vad. CUDA 12.4 already on the rig.
First server boot downloads the large-v3 CT2 model (~3 GB) to the HF cache.

## Testing

Per project convention (don't mock ASR — use a small real model + tiny fixture):

1. **`test_asr_engine.py`** — build a `FasterWhisperEngine` with `model_id=tiny`,
   `device=cpu`, `compute_type=int8`; feed a short generated speech-like WAV
   fixture; assert `transcribe()` returns ≥1 `Segment` with non-empty text. Marked
   `@pytest.mark.slow` (downloads ~75 MB tiny model once).
2. **`test_vad_endpointer.py`** — feed synthetic frames: silence → tone burst →
   silence; assert exactly one utterance is emitted and its PCM length matches the
   speech region within tolerance.
3. **`test_ws_transcribes.py`** — extend the Phase 1 WS test: inject a stub
   `ASREngine` whose `transcribe()` returns a fixed `Segment`, stream PCM through
   the WS, assert the client receives a `transcript_final` with the expected text
   and `lang`. Fast, no model download — verifies wiring, not whisper quality.
4. Existing 3 Phase 1 tests must stay green (ASR defaults to off when not injected).

E2E (no phone needed — unblocks dev despite the USB issue): a CLI WS client
streams a real multilingual WAV and prints received `transcript_final` messages.

## Non-goals (Phase 2)

- Live within-utterance partials (approach A).
- Speaker diarization (flat transcript, `speaker=None`).
- Note generation (Phase 3).
- Persisting transcripts to a store (kept in memory + sent to phone; persistence
  is a later phase).

## Risks

- **VRAM:** large-v3 fp16 ~6 GB alone — fine. When Phase 3 adds Qwen-14B the
  combined budget is ~20–23 GB of 24 GB. Tracked, not a Phase 2 blocker.
- **silero chunk size:** silero v5 wants 512-sample windows @16k; our frames are
  320 samples. `vad.py` must rebuffer. Covered by `test_vad_endpointer.py`.
- **Latency:** full large-v3 per utterance may be ~0.3–1× realtime on the GPU.
  Acceptable for final-only. If too slow, `asr.yaml` swap to `large-v3-turbo`
  (1 edit + restart).
