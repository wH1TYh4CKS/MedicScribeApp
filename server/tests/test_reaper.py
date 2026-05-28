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
