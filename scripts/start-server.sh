#!/usr/bin/env bash
# Start MedicScribe FastAPI server (loads whisper ASR + talks to llama-cpp).
# Pinned to the same single GPU as the LLM — client deployment is ONE card
# hosting both models. faster-whisper defaults to cuda:0; we pin explicitly
# so it can't drift to another card on multi-GPU dev boxes.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$SCRIPT_DIR/.."
GPU_ID="${GPU_ID:-0}"
PORT="${PORT:-8080}"

export CUDA_VISIBLE_DEVICES="$GPU_ID"

# torch (cu129 wheels) bundles its own CUDA libs under site-packages/nvidia/*/lib.
# System CUDA 12.8 at /usr/local/cuda shadows them via ldconfig, causing
# "libnvJitLink.so.12: undefined symbol __nvJitLinkGetErrorLogSize_12_9" on torch
# import. Prepend the pip CUDA lib dirs so the matching 12.9 libs win.
PY_SITE="$(python3 -c 'import site; print(site.getsitepackages()[0])')"
NV_LIBS="$(find "$PY_SITE/nvidia" -maxdepth 2 -name lib -type d 2>/dev/null | paste -sd:)"
export LD_LIBRARY_PATH="$NV_LIBS:${LD_LIBRARY_PATH:-}"

export MEDICSCRIBE_ASR_CONFIG_PATH="${MEDICSCRIBE_ASR_CONFIG_PATH:-../llm/models/asr.yaml}"
export MEDICSCRIBE_NOTE_CONFIG_PATH="${MEDICSCRIBE_NOTE_CONFIG_PATH:-../llm/models/note_llm.yaml}"
export MEDICSCRIBE_LLM_ROOT="${MEDICSCRIBE_LLM_ROOT:-../llm}"

echo "GPU   : $GPU_ID (single-GPU pinned, shared with LLM)"
echo "Port  : $PORT"

cd "$ROOT/server"
exec uvicorn medicscribe_server.main:app --host 0.0.0.0 --port "$PORT"
