#!/usr/bin/env bash
# Start the vLLM note-model server — reads model dir + serve knobs from note_llm.yaml.
# Swap models by editing llm/models/note_llm.yaml, no code change.
#
# Qwen3.8-27B is BF16 safetensors (52GB) — vLLM only.
# Served TP=4 across all four cards (52GB does not fit a 2x24GB pair). Whisper
# ASR runs on a SEPARATE card (GPU 1, pinned in start-server.sh), so the note model
# and the ASR model share the box without fighting over one GPU.

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
YAML="$SCRIPT_DIR/../llm/models/note_llm.yaml"
VENV="${VLLM_VENV:-$HOME/.venv}"   # main venv: vllm 0.19 + transformers that knows qwen3_5
                                   # (.venv-meralion's transformers is too old for Qwen3.6)

# Pull a scalar value for a yaml key at any indent; strip quotes/comments.
yval() { grep -E "^[[:space:]]*$1:" "$YAML" | head -1 | sed -E "s/^[^:]*:[[:space:]]*//; s/[[:space:]]*(#.*)?$//; s/\"//g"; }

MODEL_DIR=$(yval model_dir)
MODEL_ID=$(yval model_id)
ENDPOINT=$(yval endpoint)
GPUS=$(yval gpus)
TP=$(yval tensor_parallel)
MAXLEN=$(yval max_model_len)
GPU_UTIL=$(yval gpu_memory_utilization)
EAGER=$(yval enforce_eager)
[[ "$EAGER" == "true" ]] && EAGER_FLAG="--enforce-eager" || EAGER_FLAG=""
PORT=$(echo "$ENDPOINT" | grep -oE '[0-9]+/v1' | grep -oE '^[0-9]+')
PORT="${PORT:-8000}"

[[ -d "$MODEL_DIR" ]]      || { echo "ERROR: model dir not found: $MODEL_DIR" >&2; exit 1; }
[[ -x "$VENV/bin/vllm" ]]  || { echo "ERROR: vllm not found in $VENV (set VLLM_VENV)" >&2; exit 1; }

# torch (cu129 wheels) bundles its own CUDA libs under site-packages/nvidia/*/lib.
# System CUDA shadows them via ldconfig → "libnvJitLink.so.12: undefined symbol" on
# torch import. Prepend the pip CUDA lib dirs so the matching libs win. (Same fix as
# start-server.sh.)
PY_SITE="$("$VENV/bin/python" -c 'import site; print(site.getsitepackages()[0])')"
NV_LIBS="$(find "$PY_SITE/nvidia" -maxdepth 2 -name lib -type d 2>/dev/null | paste -sd:)"
export LD_LIBRARY_PATH="$NV_LIBS:${LD_LIBRARY_PATH:-}"

# CUDA_VISIBLE_DEVICES masks all other cards → vLLM fans TP across exactly this pair,
# keeping the split on the NVLink link (mixed-pair TP costs ~40% throughput).
export CUDA_VISIBLE_DEVICES="${GPUS:-0,2}"
# Cut allocator fragmentation on the tight 24GB cards (vLLM's own OOM hint).
export PYTORCH_ALLOC_CONF="${PYTORCH_ALLOC_CONF:-expandable_segments:True}"

echo "Model : $MODEL_DIR ($MODEL_ID)"
echo "GPUs  : $CUDA_VISIBLE_DEVICES  TP=${TP:-2}  max_len=${MAXLEN:-16384}  util=${GPU_UTIL:-0.90}"
echo "Port  : $PORT"

exec "$VENV/bin/vllm" serve "$MODEL_DIR" \
    --served-model-name "$MODEL_ID" \
    --tensor-parallel-size "${TP:-2}" \
    --max-model-len "${MAXLEN:-16384}" \
    --gpu-memory-utilization "${GPU_UTIL:-0.90}" \
    $EAGER_FLAG \
    --host 0.0.0.0 \
    --port "$PORT"
