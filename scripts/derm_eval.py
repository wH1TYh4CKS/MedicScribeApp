#!/usr/bin/env python3
"""Dermatology ASR+note eval harness.

Synthesizes the testdata/derm fixtures (piper neural TTS) if missing, optionally
overlays clinic noise (steady brown hum or competing-speaker babble), streams each
consult through the live /ws/scribe endpoint, and scores the resulting Qwen note
against per-case keywords. Synthetic audio only — no PHI.

  python scripts/derm_eval.py                       # clean
  python scripts/derm_eval.py --noise babble --level 0.6
  python scripts/derm_eval.py --noise brown  --level 0.15 --case acne

Needs: piper (pip install piper-tts) + voices in $PIPER_VOICES (default ~/piper-voices,
files <voice>.onnx). ffmpeg. The server running on $WS (default ws://localhost:8080).
"""
import argparse, asyncio, json, os, subprocess, tempfile, time, wave, websockets

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERM = os.path.join(ROOT, "testdata", "derm")
VOX = os.environ.get("PIPER_VOICES", os.path.expanduser("~/piper-voices"))
PIPER = os.environ.get("PIPER_BIN", "piper")
WS = os.environ.get("WS", "ws://localhost:8080/ws/scribe")
BABBLE = os.path.join(DERM, "babble.wav")


def _voice(tag):  # cases.json voices map dr/pt -> piper file stem
    return os.path.join(VOX, {"dr": "ryan", "pt": "amy"}[tag] + ".onnx")


def synth_fixture(case):
    """piper each turn -> concat -> clean 16k mono wav at testdata/derm/<slug>.wav."""
    out = os.path.join(DERM, case["slug"] + ".wav")
    if os.path.exists(out):
        return out
    with tempfile.TemporaryDirectory() as d:
        parts = []
        for i, (vox, text) in enumerate(case["turns"]):
            p = os.path.join(d, f"t{i}.wav")
            subprocess.run([PIPER, "-m", _voice(vox), "-f", p], input=text.encode(),
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            parts.append(p)
        lst = os.path.join(d, "l.txt")
        open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
                        "-safe", "0", "-i", lst, "-ac", "1", "-ar", "16000", out], check=True)
    return out


def with_noise(wav, mode, level, d):
    if mode == "none" or level <= 0:
        return wav
    out = os.path.join(d, "noisy.wav")
    if mode == "brown":
        ni = ["-f", "lavfi", "-i", "anoisesrc=color=brown:sample_rate=16000"]
    elif mode == "babble":
        if not os.path.exists(BABBLE):
            raise SystemExit(f"missing babble bed {BABBLE}")
        ni = ["-stream_loop", "-1", "-i", BABBLE]
    else:
        raise SystemExit(f"unknown noise {mode}")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", wav, *ni,
                    "-filter_complex",
                    f"[1]volume={level}[n];[0][n]amix=inputs=2:duration=first:normalize=0",
                    "-ac", "1", "-ar", "16000", out], check=True)
    return out


async def run_ws(wav):
    w = wave.open(wav); pcm = w.readframes(w.getnframes()); secs = w.getnframes() / 16000
    async with websockets.connect(WS, max_size=None, open_timeout=30) as ws:
        await ws.send(json.dumps({"type": "start", "session_id": f"derm{int(time.time()*1000)%100000}", "template": "soap_v1"}))
        for i in range(0, len(pcm), 65536):
            await ws.send(pcm[i:i+65536])
        await ws.send(json.dumps({"type": "stop"}))
        t0 = time.perf_counter()
        while True:
            m = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            if m["type"] == "note_done":
                return secs, m["raw_transcript"], m["note"], time.perf_counter() - t0
            if m["type"] == "error":
                return secs, None, {"err": m}, 0


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--noise", choices=["none", "brown", "babble"], default="none")
    ap.add_argument("--level", type=float, default=0.0)
    ap.add_argument("--case", help="run only this slug")
    ap.add_argument("--quiet", action="store_true", help="table only, no note dump")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(DERM, "cases.json")))
    cases = [c for c in cfg["cases"] if not a.case or c["slug"] == a.case]
    print(f"noise={a.noise} level={a.level}\n{'case':<22}{'audio':>6}{'proc':>7}{'kw':>7}  dx_ok")
    rows = []
    for c in cases:
        synth_fixture(c)
        with tempfile.TemporaryDirectory() as d:
            wav = with_noise(os.path.join(DERM, c["slug"] + ".wav"), a.noise, a.level, d)
            secs, tr, note, dt = await run_ws(wav)
        soap = (note.get("soap_text") if note and "err" not in note else "") or ""
        hay = (soap + " " + (tr or "")).lower()
        hits = [k for k in c["keywords"] if k.lower() in hay]
        dx_ok = "Y" if c["dx"].split()[-1].lower() in hay else "-"
        print(f"{c['name']:<22}{secs:>5.0f}s{dt:>6.1f}s{len(hits):>4}/{len(c['keywords'])}   {dx_ok}")
        rows.append((c, tr, soap, hits))
    if not a.quiet:
        for c, tr, soap, hits in rows:
            print("\n" + "=" * 68 + f"\nCASE {c['name']} (kw {hits})\n--- TRANSCRIPT ---\n{(tr or '')[:600]}\n--- SOAP ---\n{soap}")

asyncio.run(main())
