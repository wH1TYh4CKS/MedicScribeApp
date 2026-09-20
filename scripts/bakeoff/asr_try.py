#!/usr/bin/env python
"""ASR helper: one audio file -> one transcript, using the SAME settings as the
live server (whisper-large-v3, task=translate, params from llm/models/asr.yaml).

Runs on GPU 1 by default so the live ASR on GPU 0 is untouched. Output feeds the
note bake-off. MERaLiON (vLLM AudioLLM) is tested separately, not here.

Run via scripts/asr-try.sh.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml
from faster_whisper import WhisperModel

APP_ROOT = Path(__file__).resolve().parents[2]
ASR_YAML = APP_ROOT / "llm" / "models" / "asr.yaml"


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcribe one audio file like production does.")
    ap.add_argument("audio", type=Path, help="path to consult audio (wav/m4a/mp3)")
    ap.add_argument("--out", type=Path, default=None, help="transcript output path")
    ap.add_argument("--model", default=None, help="override model id (default: from asr.yaml)")
    args = ap.parse_args()

    if not args.audio.exists():
        print(f"ERROR: no such audio: {args.audio}", file=sys.stderr)
        return 1

    cfg = yaml.safe_load(ASR_YAML.read_text(encoding="utf-8"))
    p = cfg.get("params", {})
    model_id = args.model or cfg.get("model_id", "large-v3")

    print(f"loading {model_id} (float16, GPU 1) ...", flush=True)
    model = WhisperModel(model_id, device="cuda", compute_type="float16")

    segments, info = model.transcribe(
        str(args.audio),
        task=p.get("task", "translate"),
        beam_size=p.get("beam_size", 5),
        best_of=p.get("best_of", 5),
        temperature=p.get("temperature", 0.0),
        vad_filter=p.get("vad_filter", True),
        language=p.get("language"),
        condition_on_previous_text=p.get("condition_on_previous_text", False),
    )
    text = " ".join(s.text.strip() for s in segments).strip()

    out = args.out or args.audio.with_suffix(".transcript.txt")
    out.write_text(text, encoding="utf-8")
    print(f"\n--- transcript (detected src lang: {info.language}, p={info.language_probability:.2f}) ---")
    print(text)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
