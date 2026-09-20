#!/usr/bin/env bash
# Start the full MedicScribe stack and LEAVE IT RUNNING.
# vLLM note model (Qwen3.6-27B-FP8, TP=2 on NVLink pair 0,2) + FastAPI server
# (whisper ASR on GPU 1). Note + ASR each get their own cards — they no longer
# share one GPU. Children are setsid+nohup-detached, so the stack survives closing
# the terminal or logging out — safe to run, confirm "READY", walk out the door.
#
#   ./scripts/start-all.sh            # whisper GPU 1, note LLM gpus from yaml
#   GPU_ID=3 ./scripts/start-all.sh   # whisper on a different card
# Stop later with: ./scripts/stop-all.sh

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# venv on PATH so python/python3/uvicorn resolve under systemd too (no bashrc there).
export PATH="$HOME/.venv/bin:$PATH"
# GPU_ID = whisper/ASR card only. The note LLM no longer shares it — vLLM pins its
# own NVLink pair (gpus: in note_llm.yaml, default 0,2). Whisper sits on GPU 1.
export GPU_ID="${GPU_ID:-1}"
PIDFILE="/tmp/medicscribe-stack.pids"
: > "$PIDFILE"

start_detached() {  # $1=script  $2=logfile
    setsid nohup "$1" </dev/null >"$2" 2>&1 &
    echo $! >> "$PIDFILE"
    echo $!
}

wait_health() {  # $1=url  $2=pid  $3=label
    for _ in $(seq 1 180); do  # ~6min: vLLM 27B-FP8 load + cudagraph capture is slow cold
        curl -sf "$1" >/dev/null 2>&1 && { echo "  $3 ready."; return 0; }
        kill -0 "$2" 2>/dev/null || { echo "ERROR: $3 died on startup. Check its log." >&2; return 1; }
        sleep 2
    done
    echo "ERROR: $3 did not come up in time." >&2; return 1
}

echo "=== vLLM note model (Qwen3.6-27B-FP8, NVLink pair from yaml) ==="
LLM_PID=$(start_detached "$SCRIPT_DIR/start-llm.sh" /tmp/medicscribe-llm.log)
wait_health "http://localhost:8000/v1/models" "$LLM_PID" "LLM" || exit 1

echo "=== FastAPI server (whisper on GPU $GPU_ID) ==="
SRV_PID=$(start_detached "$SCRIPT_DIR/start-server.sh" /tmp/medicscribe-server.log)
wait_health "http://localhost:8080/health" "$SRV_PID" "Server" || { "$SCRIPT_DIR/stop-all.sh"; exit 1; }

# Tailscale reachability — the phone hits the server over the tailnet at the office.
TS_IP="$(tailscale ip -4 2>/dev/null | head -1)"
echo ""
if [ -n "$TS_IP" ] && curl -sf --max-time 5 "http://$TS_IP:8080/health" >/dev/null 2>&1; then
    TS_LINE="REACHABLE over Tailscale at $TS_IP  ✓"
else
    TS_LINE="NOT reachable over Tailscale — check 'tailscale status' before leaving  ⚠"
fi

cat <<EOF

========================================================
  MedicScribe stack READY on GPU $GPU_ID
    LLM    : http://localhost:8000/v1   log /tmp/medicscribe-llm.log
    Server : http://localhost:8080      log /tmp/medicscribe-server.log
    Phone  : $TS_LINE
  PIDs saved to $PIDFILE — survives logout.
  Stop with: ./scripts/stop-all.sh
========================================================
EOF
