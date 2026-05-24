"""ASR package.

Only the lightweight contract (`base`) is imported eagerly. The whisper engine,
silero VAD, and registry pull heavy deps (faster-whisper, torch, numpy) and are
imported lazily from `medicscribe_server.asr.registry` on the lifespan path, so
importing this package costs nothing when ASR is disabled.
"""

from medicscribe_server.asr.base import ASREngine, Segment

__all__ = ["ASREngine", "Segment"]
