#!/usr/bin/env bash
# Stop the MedicScribe stack started by start-all.sh.
set -uo pipefail
PIDFILE="/tmp/medicscribe-stack.pids"

if [ -f "$PIDFILE" ]; then
    while read -r pid; do
        [ -n "$pid" ] && kill "$pid" 2>/dev/null && echo "stopped PID $pid"
    done < "$PIDFILE"
    rm -f "$PIDFILE"
fi
# Belt-and-suspenders: kill by pattern in case PIDs drifted. vLLM TP=2 spawns
# worker subprocesses (TP=4) that outlive the parent and keep holding GPU VRAM, so target
# the model path too (kept in sync with note_llm.yaml model_dir) — that catches the EngineCore/worker procs the parent missed.
pkill -f "vllm serve" 2>/dev/null && echo "stopped stray vllm" || true
pkill -f "Qwen__Qwen3.8-27B" 2>/dev/null && echo "stopped stray vllm workers" || true
pkill -f "uvicorn medicscribe_server" 2>/dev/null && echo "stopped stray uvicorn" || true
echo "MedicScribe stack stopped."
# Verify GPUs actually released (vLLM workers are stubborn). Warn, don't fail.
sleep 2
for g in 0 1 2 3; do
    used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits -i "$g" 2>/dev/null)
    [ -n "$used" ] && [ "$used" -gt 500 ] && echo "  ⚠ GPU $g still holds ${used}MiB — check for orphaned workers" >&2
done
