"""Slow smoke test for the silero-VAD endpointer.

Verifies the streaming mechanics (frame rebuffering to 512-sample windows,
accept/pop/flush lifecycle) load and run against the real silero model without
crashing. A synthetic tone is not guaranteed to be flagged as speech by silero,
so utterance detection is exercised but not strictly asserted. Marked `slow`.
"""

import math
import struct

import pytest


def _pcm(seconds: float, freq: int = 0, sr: int = 16000) -> bytes:
    n = int(seconds * sr)
    if freq == 0:
        return b"\x00\x00" * n
    return struct.pack(
        "<" + "h" * n,
        *[int(32767 * 0.4 * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)],
    )


@pytest.mark.slow
def test_endpointer_mechanics_no_crash():
    from medicscribe_server.asr.vad import Endpointer

    ep = Endpointer(min_silence_ms=300)
    audio = _pcm(0.3) + _pcm(0.6, 300) + _pcm(0.6)
    frame = 640
    for i in range(0, len(audio), frame):
        ep.accept(audio[i : i + frame])
    utts = []
    while (u := ep.pop_utterance()) is not None:
        utts.append(u)
    tail = ep.flush()
    if tail:
        utts.append(tail)
    assert isinstance(utts, list)
    for u in utts:
        assert isinstance(u, (bytes, bytearray))


@pytest.mark.slow
def test_endpointer_rejects_non_16k():
    from medicscribe_server.asr.vad import Endpointer

    with pytest.raises(ValueError):
        Endpointer(sample_rate=8000)
