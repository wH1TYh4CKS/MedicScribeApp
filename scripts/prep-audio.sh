#!/usr/bin/env bash
# Normalize any audio/video (mp4, m4a, mp3, wav…) to 16 kHz mono WAV — the format
# both ASR paths expect. One job: convert. Prints the output wav path.
#
#   ./scripts/prep-audio.sh testdata/consult.mp4
#   -> testdata/consult.wav
set -euo pipefail
in="${1:?usage: prep-audio.sh <input audio/video>}"
[ -f "$in" ] || { echo "ERROR: no such file: $in" >&2; exit 1; }
out="${in%.*}.wav"
ffmpeg -hide_banner -loglevel error -y -i "$in" -ac 1 -ar 16000 -vn "$out"
echo "$out"
