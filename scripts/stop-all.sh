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
# Belt-and-suspenders: kill by pattern in case PIDs drifted.
pkill -f "llama_cpp.server" 2>/dev/null && echo "stopped stray llama-cpp" || true
pkill -f "uvicorn medicscribe_server" 2>/dev/null && echo "stopped stray uvicorn" || true
echo "MedicScribe stack stopped."
