#!/usr/bin/env python
"""Note-gen bake-off: one transcript -> every candidate model -> one COMPARISON.md.

Faithful to production: renders the SAME sum_v1 template and calls the SAME
OpenAICompatClient the live server uses. Only the model swaps.

Runs each model on FREE GPUs (default GPU 1, NVLink pair 1,3 for the 70B) so the
live site on GPU 0 is never touched. One model at a time: load -> infer -> kill.

Run via scripts/note-bakeoff.sh (sets PYTHONPATH + the app venv).
"""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

from medicscribe_server.llm_client.openai_compat import OpenAICompatClient
from medicscribe_server.notes.template import NoteTemplate

APP_ROOT = Path(__file__).resolve().parents[2]          # MedicScribeApp/
LLM_ROOT = APP_ROOT / "llm"
MODELS_DIR = Path.home() / "llm_workflow" / "data" / "models"
LLAMA_PY = str(Path.home() / ".venv" / "bin" / "python")  # venv that has llama_cpp
PORT = 8011                                              # NOT 8000 (live LLM owns that)
N_CTX = 8192

# Production note-gen params (mirrors note_llm.yaml — same for every model = fair).
PARAMS = {"temperature": 0.0, "top_p": 1.0, "max_tokens": 1024}

# name -> (gguf relpath under MODELS_DIR, llama chat_format, CUDA_VISIBLE_DEVICES)
MODELS: list[tuple[str, str, str, str]] = [
    ("qwen2.5-14b-baseline", "qwen2.5-14b-gguf/Qwen2.5-14B-Instruct-Q4_K_M.gguf", "chatml", "1"),
    ("medical-notes-1b",     "medical-notes-1b-gguf/Llama3.2-Medical-Notes-1B.Q5_K_M.gguf", "llama-3", "1"),
    ("med42-8b",             "med42-8b-gguf/Llama3-Med42-8B.Q5_K_M.gguf", "llama-3", "1"),
    ("medgemma-27b",         "medgemma-27b-gguf/medgemma-27b-text-it-Q5_K_M.gguf", "gemma", "1"),
    ("openbiollm-70b",       "openbiollm-70b-gguf/Llama3-OpenBioLLM-70B.Q4_K_M.gguf", "llama-3", "1,3"),
]


def wait_health(url: str, proc: subprocess.Popen, timeout_s: int) -> bool:
    """Poll /models until the server answers or the process dies."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            return False
        try:
            if httpx.get(url, timeout=2.0).status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(2)
    return False


def run_one(name: str, gguf: Path, chat_format: str, gpus: str, prompt: str, schema: dict) -> dict:
    """Boot a llama-cpp server for one model, generate the note, tear it down."""
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpus)
    cmd = [
        LLAMA_PY, "-m", "llama_cpp.server",
        "--model", str(gguf), "--host", "127.0.0.1", "--port", str(PORT),
        "--n_gpu_layers", "-1", "--n_ctx", str(N_CTX),
        "--chat_format", chat_format, "--verbose", "false",
    ]
    t0 = time.monotonic()
    proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        # 70B on two cards can take a while to load; give big models more runway.
        load_budget = 600 if gpus != "1" or "70b" in name else 240
        if not wait_health(f"http://127.0.0.1:{PORT}/v1/models", proc, load_budget):
            return {"ok": False, "error": "server did not come up", "load_s": time.monotonic() - t0}
        load_s = time.monotonic() - t0
        client = OpenAICompatClient(
            endpoint=f"http://127.0.0.1:{PORT}/v1", model=name, params=PARAMS,
            timeout=120.0, guided=False, text_field="soap_text",
        )
        g0 = time.monotonic()
        note = client.complete_json(prompt, schema)["soap_text"]
        client.close()
        return {"ok": True, "note": note, "load_s": load_s, "gen_s": time.monotonic() - g0}
    except Exception as exc:  # noqa: BLE001 — bake-off tool, surface any failure per-model
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "load_s": time.monotonic() - t0}
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=20)
        except Exception:  # noqa: BLE001
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:  # noqa: BLE001
                pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Note-gen bake-off across candidate models.")
    ap.add_argument("transcript", type=Path, help="path to transcript .txt")
    ap.add_argument("--only", nargs="*", help="subset of model names to run")
    ap.add_argument("--outdir", type=Path, default=None)
    args = ap.parse_args()

    transcript = args.transcript.read_text(encoding="utf-8").strip()
    if not transcript:
        print("ERROR: transcript is empty", file=sys.stderr)
        return 1

    template = NoteTemplate.load("sum_v1", LLM_ROOT)
    prompt, schema = template.render(transcript)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = args.outdir or (LLM_ROOT / "eval" / "bakeoff" / stamp)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "transcript.txt").write_text(transcript, encoding="utf-8")

    models = [m for m in MODELS if not args.only or m[0] in args.only]
    results: list[tuple[str, dict]] = []
    for name, rel, chat_format, gpus in models:
        gguf = MODELS_DIR / rel
        if not gguf.exists():
            print(f"SKIP {name}: not downloaded yet ({rel})")
            results.append((name, {"ok": False, "error": "not downloaded"}))
            continue
        print(f"RUN  {name}  (GPU {gpus}, {chat_format}) ...", flush=True)
        res = run_one(name, gguf, chat_format, gpus, prompt, schema)
        if res["ok"]:
            print(f"  done: load {res['load_s']:.0f}s, gen {res['gen_s']:.0f}s")
            (outdir / f"{name}.md").write_text(res["note"], encoding="utf-8")
        else:
            print(f"  FAIL: {res['error']}")
        results.append((name, res))

    # Assemble the comparison sheet.
    lines = [f"# Note-gen bake-off — {stamp}", "",
             "Same transcript, same sum_v1 prompt, one model each. Score with",
             "`llm/eval/note_quality_rubric.md`.", "",
             "## Transcript", "```", transcript, "```", "",
             "## Speed", "", "| model | load | gen |", "|---|---|---|"]
    for name, res in results:
        if res.get("ok"):
            lines.append(f"| {name} | {res['load_s']:.0f}s | {res['gen_s']:.0f}s |")
        else:
            lines.append(f"| {name} | — | {res.get('error','skipped')} |")
    lines += ["", "## Notes", ""]
    for name, res in results:
        lines += [f"### {name}", ""]
        if res.get("ok"):
            lines += ["```", res["note"], "```", ""]
        else:
            lines += [f"_{res.get('error','skipped')}_", ""]
    (outdir / "COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")

    print(f"\nWrote {outdir/'COMPARISON.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
