"""Direct unit tests for WavWriter.

Originally the WS integration test inspected the WAV file post-stop to confirm
format. With PDPA-driven WAV deletion at stop, that assertion moved here so we
keep coverage of the writer's actual bytes-on-disk shape.
"""

import struct
import wave

from medicscribe_server.store.audio_writer import WavWriter


def test_writer_emits_valid_mono_16khz_16bit_wav(tmp_path):
    wav_path = tmp_path / "out.wav"
    # 1 s of silence: 16000 frames * 2 bytes
    one_second = struct.pack("<" + "h" * 16000, *([0] * 16000))

    with WavWriter(wav_path) as w:
        w.write(one_second)

    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 16000
        assert wf.getsampwidth() == 2
        assert wf.getnframes() == 16000


def test_duration_seconds_tracks_written_bytes(tmp_path):
    wav_path = tmp_path / "out.wav"
    quarter_second = b"\x00\x00" * 4000  # 4000 frames = 0.25 s @ 16 kHz mono
    w = WavWriter(wav_path)
    w.write(quarter_second)
    assert abs(w.duration_seconds() - 0.25) < 1e-6
    w.close()
