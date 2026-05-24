from __future__ import annotations

import numpy as np

# silero v5 requires fixed-size windows at 16 kHz.
_WINDOW_SAMPLES = 512
_WINDOW_BYTES = _WINDOW_SAMPLES * 2  # 16-bit PCM


class Endpointer:
    """Streaming speech endpointer over silero-VAD.

    Accepts arbitrary-length 16-bit mono PCM frames (the wire sends 20 ms / 640 B
    frames), rebuffers them into the 512-sample windows silero requires, and
    accumulates speech into utterances. A completed utterance becomes available
    once trailing silence exceeds ``min_silence_ms``.

    Usage:
        ep.accept(frame_bytes)
        while (utt := ep.pop_utterance()) is not None:
            transcribe(utt)
        ...
        tail = ep.flush()  # drain partial speech at Stop
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_silence_ms: int = 500,
        speech_pad_ms: int = 30,
    ) -> None:
        # Imported lazily so the server can boot without torch when ASR is off.
        from silero_vad import VADIterator, load_silero_vad

        if sample_rate != 16000:
            raise ValueError("Endpointer supports 16 kHz only")
        self._model = load_silero_vad()
        self._it = VADIterator(
            self._model,
            threshold=threshold,
            sampling_rate=sample_rate,
            min_silence_duration_ms=min_silence_ms,
            speech_pad_ms=speech_pad_ms,
        )
        self._pcm_buf = bytearray()
        self._utt = bytearray()
        self._in_speech = False
        self._completed: list[bytes] = []

    def accept(self, frame: bytes) -> None:
        import torch

        self._pcm_buf.extend(frame)
        while len(self._pcm_buf) >= _WINDOW_BYTES:
            window = bytes(self._pcm_buf[:_WINDOW_BYTES])
            del self._pcm_buf[:_WINDOW_BYTES]
            arr = np.frombuffer(window, dtype=np.int16).astype(np.float32) / 32768.0
            out = self._it(torch.from_numpy(arr))
            if out is not None and "start" in out:
                self._in_speech = True
                self._utt = bytearray()
            if out is not None and "end" in out:
                if self._in_speech:
                    self._utt.extend(window)
                self._in_speech = False
                if self._utt:
                    self._completed.append(bytes(self._utt))
                self._utt = bytearray()
                continue
            if self._in_speech:
                self._utt.extend(window)

    def pop_utterance(self) -> bytes | None:
        """Return the oldest completed utterance PCM, or None."""
        if self._completed:
            return self._completed.pop(0)
        return None

    def flush(self) -> bytes | None:
        """Return any in-progress speech PCM and reset the iterator (call on Stop)."""
        tail = bytes(self._utt) if self._utt else None
        self._utt = bytearray()
        self._pcm_buf = bytearray()
        self._in_speech = False
        self._it.reset_states()
        return tail
