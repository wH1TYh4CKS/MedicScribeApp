from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel

from medicscribe_server.asr.base import ASREngine, Segment


class FasterWhisperEngine(ASREngine):
    def __init__(
        self,
        model_id: str,
        device: str = 'cuda',
        compute_type: str = 'float16',
        params: dict | None = None,
    ) -> None:
        self._params = params or {}
        self.model = WhisperModel(model_id, device=device, compute_type=compute_type)

    def transcribe(self, pcm: bytes, sample_rate: int) -> list[Segment]:
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        # Skip sub-0.3s blips: too short for language detection (auto-detect raises
        # "max() iterable argument is empty") and only yield Whisper hallucinations.
        if audio.size < int(sample_rate * 0.3):
            return []

        p = self._params
        try:
            segments, info = self.model.transcribe(
                audio,
                beam_size=p.get('beam_size', 5),
                best_of=p.get('best_of', 5),
                temperature=p.get('temperature', 0.0),
                language=p.get('language'),
                task=p.get('task', 'transcribe'),
                vad_filter=p.get('vad_filter', True),
                initial_prompt=p.get('initial_prompt'),
                # False stops large-v3 looping/repeating on longer utterances.
                condition_on_previous_text=p.get('condition_on_previous_text', True),
                # Auto-detect (language: null) otherwise reads ONE 30s window and
                # locks the whole consult to that guess. On a real Mandarin derm
                # consult it guessed Malay at p=0.62 and rendered 22 minutes of
                # Hanzi speech as Malay prose. A threshold makes it keep scanning
                # until a window clears the bar, then majority-vote across them.
                # Both keys are required: without a threshold the loop always
                # breaks on the first window and `segments` has no effect.
                language_detection_segments=p.get('language_detection_segments', 8),
                language_detection_threshold=p.get('language_detection_threshold', 0.7),
            )
        except ValueError:
            # faster-whisper auto-detect can still raise on degenerate audio.
            # Never let it kill the live WebSocket session.
            return []

        result = []
        for s in segments:
            t = s.text.strip()
            if t:
                result.append(
                    Segment(text=t, lang=info.language, t0=float(s.start), t1=float(s.end))
                )
        return result

    def close(self) -> None:
        self.model = None
