#!/usr/bin/env bash
# Start full MedicScribe stack on a SINGLE GPU: llama-cpp LLM + FastAPI server.
# Both pin to GPU_ID (default 0). This is the client deployment shape — one card
# hosts both ASR (whisper) and the note model. Run from project root.
#   ./scripts/start-all.sh          # GPU 0
#   GPU_ID=1 ./scripts/start-all.sh # different card

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GPU_ID="${GPU_ID:-0}"

echo "=== Starting llama-cpp LLM server (GPU $GPU_ID) ==="
"$SCRIPT_DIR/start-llm.sh" > /tmp/medicscribe-llm.log 2>&1 &
LLM_PID=$!

echo "=== Waiting for LLM server (up to 120s) ==="
for i in $(seq 1 60); do
    if curl -sf http://localhost:8000/v1/models > /dev/null 2>&1; then
        echo "LLM server ready."
        break
    fi
    if ! kill -0 "$LLM_PID" 2>/dev/null; then
        echo "ERROR: LLM server died on startup. See /tmp/medicscribe-llm.log" >&2
        exit 1
    fi
    sleep 2
done

echo "=== Starting MedicScribe FastAPI server (GPU $GPU_ID) ==="
"$SCRIPT_DIR/start-server.sh" > /tmp/medicscribe-server.log 2>&1 &
SERVER_PID=$!

echo "=== Waiting for FastAPI server (loads whisper, up to 120s) ==="
for i in $(seq 1 60); do
    if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
        echo "FastAPI server ready."
        break
    fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "ERROR: FastAPI server died on startup. See /tmp/medicscribe-server.log" >&2
        kill "$LLM_PID" 2>/dev/null || true
        exit 1
    fi
    sleep 2
done

echo ""
echo "Stack running on GPU $GPU_ID:"
echo "  LLM    : http://localhost:8000/v1   (PID $LLM_PID,    log /tmp/medicscribe-llm.log)"
echo "  Server : http://localhost:8080      (PID $SERVER_PID, log /tmp/medicscribe-server.log)"
echo ""
echo "Stop: kill $LLM_PID $SERVER_PID"
