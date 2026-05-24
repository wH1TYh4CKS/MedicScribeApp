from __future__ import annotations
from pathlib import Path
import yaml
from medicscribe_server.asr.base import ASREngine
from medicscribe_server.asr.faster_whisper_engine import FasterWhisperEngine
from medicscribe_server.asr.vad import Endpointer

def load_asr_config(config_path: Path) -> dict:
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def build_asr(config_path: Path) -> ASREngine:
    cfg = load_asr_config(config_path)
    engine = cfg['engine']
    if engine in ('faster-whisper', 'faster_whisper'):
        return FasterWhisperEngine(
            model_id=cfg['model_id'],
            device=cfg.get('device', 'cuda'),
            compute_type=cfg.get('compute_type', 'float16'),
            params=cfg.get('params', {})
        )
    raise ValueError(f'unknown ASR engine: {engine}')

def build_endpointer(config_path: Path) -> Endpointer:
    cfg = load_asr_config(config_path)
    v = cfg.get('vad', {})
    return Endpointer(
        sample_rate=16000,
        threshold=float(v.get('threshold', 0.5)),
        min_silence_ms=int(v.get('min_silence_ms', 500))
    )
