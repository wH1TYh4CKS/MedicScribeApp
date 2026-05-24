from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel
from medicscribe_server.asr.base import ASREngine, Segment


class FasterWhisperEngine(ASREngine):
    def __init__(self, model_id: str, device: str = 'cuda', compute_type: str = 'float16', params: dict | None = None) -> None:
        self._params = params or {}
        self.model = WhisperModel(model_id, device=device, compute_type=compute_type)

    def transcribe(self, pcm: bytes, sample_rate: int) -> list[Segment]:
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        if audio.size == 0:
            return []
        
        p = self._params
        segments, info = self.model.transcribe(
            audio,
            beam_size=p.get('beam_size', 5),
            best_of=p.get('best_of', 5),
            temperature=p.get('temperature', 0.0),
            language=None,
            task=p.get('task', 'transcribe'),
            vad_filter=p.get('vad_filter', True),
            initial_prompt=p.get('initial_prompt')
        )
        
        result = []
        for s in segments:
            t = s.text.strip()
            if t:
                result.append(Segment(text=t, lang=info.language, t0=float(s.start), t1=float(s.end)))
        return result

    def close(self) -> None:
        self.model = None
