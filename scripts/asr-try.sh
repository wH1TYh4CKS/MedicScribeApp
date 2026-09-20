#!/usr/bin/env bash
# Transcribe one audio file with the production whisper settings, on GPU 1 (live
# ASR on GPU 0 untouched). Writes <audio>.transcript.txt — feed it to note-bakeoff.
#
#   ./scripts/asr-try.sh consult.wav
set -euo pipefail
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_ROOT"
export CUDA_VISIBLE_DEVICES=1     # free card; keep GPU 0 for the live site
PYTHONPATH="server/src" exec server/.venv/bin/python scripts/bakeoff/asr_try.py "$@"
