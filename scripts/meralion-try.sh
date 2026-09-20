#!/usr/bin/env bash
# Transcribe one audio file with MERaLiON-3-3B-ASR (vLLM sidecar) on GPU 1 (live
# ASR on GPU 0 untouched). Writes <audio>.meralion.txt — diff against asr-try.sh.
# Uses the dedicated ~/.venv-meralion (the app venv must NOT be touched).
#
#   ./scripts/meralion-try.sh consult.wav
set -euo pipefail
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_ROOT"
exec ~/.venv-meralion/bin/python scripts/bakeoff/meralion_try.py "$@"
