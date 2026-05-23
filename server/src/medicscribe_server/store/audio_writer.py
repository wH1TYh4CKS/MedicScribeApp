import wave
from pathlib import Path


class WavWriter:
    def __init__(
        self,
        path: Path,
        sample_rate: int = 16000,
        channels: int = 1,
        sample_width: int = 2,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        self._wave = wave.open(str(path), "wb")
        self._wave.setnchannels(channels)
        self._wave.setsampwidth(sample_width)
        self._wave.setframerate(sample_rate)
        self._bytes_written = 0

    @property
    def path(self) -> Path:
        return self._path

    def write(self, pcm: bytes) -> None:
        self._wave.writeframes(pcm)
        self._bytes_written += len(pcm)

    def duration_seconds(self) -> float:
        framerate = self._wave.getframerate()
        channels = self._wave.getnchannels()
        sample_width = self._wave.getsampwidth()
        if framerate == 0:
            return 0.0
        return self._bytes_written / (framerate * channels * sample_width)

    def close(self) -> None:
        self._wave.close()

    def __enter__(self) -> "WavWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
