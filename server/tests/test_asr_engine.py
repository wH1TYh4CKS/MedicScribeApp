"""Slow smoke test for the real faster-whisper engine.

Uses the `tiny` model on CPU/int8 so it runs anywhere without a GPU or the 3 GB
large-v3 download. Asserts the engine loads, runs, and returns well-formed
`Segment`s — it does NOT assert transcription quality (a pure tone has no words;
real Manglish accuracy is verified via the live phone loop). Marked `slow`:
run with `pytest -m slow`.
"""

import math
import struct

import pytest

from medicscribe_server.asr.base import Segment


def _tone_pcm(seconds: float, freq: int = 440, sr: int = 16000) -> bytes:
    n = int(seconds * sr)
    return struct.pack(
        "<" + "h" * n,
        *[int(32767 * 0.3 * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)],
    )


@pytest.mark.slow
def test_engine_loads_and_returns_segments():
    from medicscribe_server.asr.faster_whisper_engine import FasterWhisperEngine

    engine = FasterWhisperEngine(
        model_id="tiny",
        device="cpu",
        compute_type="int8",
        params={"beam_size": 1, "best_of": 1, "vad_filter": False},
    )
    try:
        segs = engine.transcribe(_tone_pcm(1.0), 16000)
    finally:
        engine.close()
    assert isinstance(segs, list)
    for s in segs:
        assert isinstance(s, Segment)
        assert isinstance(s.text, str)


@pytest.mark.slow
def test_engine_empty_pcm_returns_empty():
    from medicscribe_server.asr.faster_whisper_engine import FasterWhisperEngine

    engine = FasterWhisperEngine(model_id="tiny", device="cpu", compute_type="int8")
    try:
        assert engine.transcribe(b"", 16000) == []
    finally:
        engine.close()
