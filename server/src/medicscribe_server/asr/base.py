from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class Segment:
    """One recognized span of speech."""

    text: str
    lang: str | None = None
    t0: float = 0.0
    t1: float = 0.0


class ASREngine(ABC):
    """Contract for a speech-to-text backend.

    Implementations transcribe a single completed utterance of 16-bit signed
    little-endian PCM. Language is auto-detected (never forced) so code-switched
    Manglish is preserved.
    """

    @abstractmethod
    def transcribe(self, pcm: bytes, sample_rate: int) -> list[Segment]:
        """Transcribe one utterance. Returns [] for silence/no speech."""

    def close(self) -> None:  # noqa: B027  # optional hook, default no-op
        """Release model resources. Override if the backend holds GPU memory."""
