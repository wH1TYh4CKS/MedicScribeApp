#!/usr/bin/env python
"""ASR test for MERaLiON-3-3B-ASR — counterpart to asr_try.py (whisper).

MERaLiON is a speech-LLM, not a whisper model. Recommended path is the
`meralion-3-asr` package: a FastAPI sidecar over an internal `vllm serve`,
exposing OpenAI-style /v1/audio/transcriptions (30 s auto-chunk, audio-only).

This boots that sidecar on GPU 1 (live ASR on GPU 0 untouched), POSTs one audio
file, prints + saves the transcript, then tears the server down. Diff its output
against asr-try.sh's whisper transcript on the same Manglish consult.

Runs in its OWN venv (~/.venv-meralion) — the app venv's transformers is pinned
incompatibly and must not be touched (it serves the live site).

License note: MERaLiON-3 terms are TBD — internal testing only for now.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

MODEL_DIR = Path.home() / "llm_workflow" / "data" / "models" / "meralion-3-3b-asr"
CLI = str(Path.home() / ".venv-meralion" / "bin" / "meralion-3-asr")
PORT = 8021                      # sidecar port (NOT 8000/8011 — those are taken)
SERVED_NAME = "meralion-3-3b-asr"
SERVE_LOG = "/tmp/meralion-serve.log"


def wait_ready(audio: Path, proc: subprocess.Popen, timeout_s: int) -> httpx.Response | None:
    """Retry the real transcription until the sidecar+vLLM are up (or timeout)."""
    url = f"http://127.0.0.1:{PORT}/v1/audio/transcriptions"
    deadline = time.monotonic() + timeout_s
    last = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            print(f"ERROR: serve process exited early (code {proc.returncode}); see {SERVE_LOG}",
                  file=sys.stderr)
            return None
        try:
            with open(audio, "rb") as fh:
                r = httpx.post(url, files={"file": (audio.name, fh, "audio/wav")},
                               data={"model": SERVED_NAME}, timeout=120.0)
            if r.status_code == 200:
                return r
            last = f"{r.status_code}: {r.text[:200]}"
        except httpx.HTTPError as exc:
            last = str(exc)
        time.sleep(5)
    print(f"ERROR: not ready in {timeout_s}s. last: {last}", file=sys.stderr)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Transcribe one file with MERaLiON-3-3B-ASR.")
    ap.add_argument("audio", type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--timeout", type=int, default=360, help="server startup budget (s)")
    args = ap.parse_args()

    if not args.audio.exists():
        print(f"ERROR: no such audio: {args.audio}", file=sys.stderr)
        return 1
    if not (MODEL_DIR / "config.json").exists():
        print(f"ERROR: model not downloaded at {MODEL_DIR}", file=sys.stderr)
        return 1

    env = dict(os.environ, CUDA_VISIBLE_DEVICES="1")   # free card; keep GPU 0 live
    cmd = [CLI, "serve", "--model", str(MODEL_DIR), "--served-model-name", SERVED_NAME,
           "--host", "127.0.0.1", "--port", str(PORT), "--internal-port", "0",
           "--gpu-memory-utilization", "0.5", "--internal-log", SERVE_LOG]
    print(f"starting meralion-3-asr serve on GPU 1, port {PORT} (vLLM load ~1-2 min) ...", flush=True)
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        resp = wait_ready(args.audio, proc, args.timeout)
        if resp is None:
            return 1
        body = resp.json()
        text = (body.get("text") if isinstance(body, dict) else str(body)).strip()
        out = args.out or args.audio.with_suffix(".meralion.txt")
        out.write_text(text, encoding="utf-8")
        print("\n--- MERaLiON transcript ---")
        print(text or "(empty)")
        print(f"\nwrote {out}")
        return 0
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=30)
        except Exception:  # noqa: BLE001
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    raise SystemExit(main())
