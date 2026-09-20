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
