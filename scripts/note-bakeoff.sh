#!/usr/bin/env bash
# Note-gen bake-off wrapper. Runs the driver under the APP venv (which has the
# medicscribe_server package + jinja2/httpx/jsonschema), with server/src on the
# path. The driver itself spawns llama-cpp servers from ~/.venv on free GPUs.
#
#   ./scripts/note-bakeoff.sh path/to/transcript.txt
#   ./scripts/note-bakeoff.sh transcript.txt --only med42-8b medgemma-27b
set -euo pipefail
APP_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$APP_ROOT"
PYTHONPATH="server/src" exec server/.venv/bin/python scripts/bakeoff/note_bakeoff.py "$@"
