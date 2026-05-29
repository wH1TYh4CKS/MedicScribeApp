#!/usr/bin/env bash
# Start llama-cpp inference server — reads model path + port from note_llm.yaml.
# Swap models by editing llm/models/note_llm.yaml (model_file + endpoint), no code change.
#
# SINGLE-GPU by design: client deployment is one GPU hosting BOTH the ASR model
# (whisper, loaded by the FastAPI server) and this doc model. We pin to one GPU
# via CUDA_VISIBLE_DEVICES so llama-cpp cannot fan the model out across cards.
# Qwen2.5-14B Q4_K_M (~9GB) + whisper-large-v3 fp16 (~4GB) fits in a 24GB card.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YAML="$SCRIPT_DIR/../llm/models/note_llm.yaml"

MODEL_FILE=$(grep '^model_file:' "$YAML" | awk '{print $2}')
ENDPOINT=$(grep '^endpoint:' "$YAML" | awk '{print $2}')
PORT=$(echo "$ENDPOINT" | grep -oE '[0-9]+/v1$' | cut -d'/' -f1)
PORT="${PORT:-8000}"
GPU_LAYERS="${GPU_LAYERS:--1}"        # -1 = all layers on GPU; override via env
GPU_ID="${GPU_ID:-0}"                 # which single GPU to use; override via env
N_CTX="${N_CTX:-8192}"                # context window; default 2048 truncates long consults

if [[ -z "$MODEL_FILE" ]]; then
    echo "ERROR: model_file not set in $YAML" >&2; exit 1
fi
if [[ ! -f "$MODEL_FILE" ]]; then
    echo "ERROR: model not found: $MODEL_FILE" >&2; exit 1
fi

echo "Model : $MODEL_FILE"
echo "Port  : $PORT"
echo "Layers: $GPU_LAYERS"
echo "GPU   : $GPU_ID (single-GPU pinned)"

# CUDA_VISIBLE_DEVICES masks all other GPUs → llama-cpp sees one card, can't split.
export CUDA_VISIBLE_DEVICES="$GPU_ID"

exec python -m llama_cpp.server \
    --model "$MODEL_FILE" \
    --host 0.0.0.0 \
    --port "$PORT" \
    --n_gpu_layers "$GPU_LAYERS" \
    --n_ctx "$N_CTX" \
    --split_mode 0 \
    --main_gpu 0 \
    --chat_format chatml \
    --verbose false
