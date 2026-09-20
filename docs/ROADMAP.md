# MedicScribe — Next-Stage Development

Backlog of work that makes the **pitch / overview claims true**. Each item below is currently
stated (or implied) in the client-facing docs but **not yet built**, so it is committed here as
next-stage dev. Ordered by how exposed the claim is in front of a corporate client.

> Source of the gap list: doc audit on 2026-05-30 against the live code
> (`app/tablet`, `server/src`, `llm/models/asr.yaml`). Effort = solo-dev estimate.

---

## Delivery buckets

**A · Ready now (the demo, off-the-shelf):** record → SOAP → share, multilingual code-switch
(EN/MS/ZH/TA + Manglish) → English note, privacy wipe / export-only, Android client.

**B · 1-month buildable (Tier-2 single-clinic standard):** note editing, PDF/DOCX export,
headless+systemd appliance, iPad/iOS web client, queued multi-session (2–3 docs), PDPA audit
trail. All of P0 + the easy P1 fit inside the pitch's "30 days after requirement finalisation"
for one clinic.

**C · Build-for-them / needs scoping (NOT a blind 1-month promise):** genuine MY-tuned ASR
(reword instead unless funded), true 3–5 doctors in parallel (multi-GPU orchestration),
custom EMR/CMS integration (depends entirely on their software). Size these once requirements land.

> The 30-day deployment promise is realistic for **Bucket B (Tier-2 single clinic)**.
> Tier-3 parallel and custom EMR are **Bucket C** — scope, don't promise blind.

---

## P0 — "False today" (highest priority: directly disprovable in a demo) · Bucket B

### 1. iPad / iOS client — **Effort: 1–2 weeks (long pole)**
- **Doc claim:** "fully compatible with both iPad (iOS) and Android tablets."
- **Reality now:** only the Android client exists (`app/tablet`). No iOS app.
- **Plan:** ship the iOS path described in Overview §8 — run the recorder as a **secure local
  web app (HTTPS)** served by the clinic server, opened in Safari, with a one-time **CA
  certificate** install per device. Reuses the existing server WS/ASR/note pipeline; only a
  browser recorder (WebAudio mic capture → WebSocket) + cert provisioning is new.
- **Done when:** an iPad on the clinic network can record → get a SOAP note end-to-end.

### 2. In-app note editing — **Effort: 1–2 days (easy)**
- **Doc claim:** "review, **edit**, and export."
- **Reality now:** `NotePage.kt` is read-only — no text fields, no edit path.
- **Plan:** make the SOAP sections editable (per-section `TextField`) before Share/Export;
  preserve the point-form rendering.
- **Done when:** a doctor can correct a line in the note on-device before sharing.

### 3. Real export (PDF / DOCX) — **Effort: 3–5 days**
- **Doc claim (overview history):** "export PDF / DOCX / JSON."
- **Reality now:** "Share" = `Intent.ACTION_SEND` with **plain text** only — no document export.
- **Plan:** add PDF (Android `PrintAttributes`/print framework) and DOCX (Apache POI) export
  alongside the existing text share.
- **Done when:** the note can be exported as a formatted PDF and a DOCX file.

---

## P1 — Overclaims to back with real capability

### 4. Malaysian-tuned ASR (or reword the claim) — **Effort: open-ended → Bucket C (or reword now)**
- **Doc claim:** "speech-recognition models tuned for Malaysian multilingual consultations."
- **Reality now:** stock `large-v3` + `task=translate` (the Malaysian fine-tune was rejected —
  see `asr.yaml`). Handles Manglish code-switch well, but is not a Malaysian-tuned model.
- **Plan:** either (a) source/train an ASR model genuinely tuned on Malaysian code-switched +
  dialect speech that can also emit the needed scripts — training + data + eval, **not a
  1-month task**; or (b) keep the wording honest ("advanced multilingual models that handle
  Malaysian code-switched speech"). **Default: reword** unless a client funds tuning.

### 5. Multi-doctor concurrency (backs Tier 3) — **Effort: ~1 week queued (2–3) / Bucket C for true 3–5 parallel**
- **Doc claim:** "scale seamlessly based on volume and simultaneous user requirements" /
  Overview Tier 3 "3–5 doctors simultaneously."
- **Reality now:** `session.py` serialises Whisper calls ("engine not safe under concurrent
  use"); single GPU, single stream.
- **Plan:** queued/batched inference for 2–3 docs (~1 week, Bucket B-ish); true 3–5 parallel
  needs multi-GPU orchestration on the 4×3090 rig — real engineering, **Bucket C**. Required
  before selling Tier 3.

### 6. Sealed headless appliance + auto-start — **Effort: 2–4 days (mostly ops) · Bucket B**
- **Doc claim:** "sealed, headless appliance… zero tinkering, zero maintenance… it simply runs."
- **Reality now:** runs off manual `scripts/start-all.sh`; no systemd units; the dev box has
  Xorg/desktop.
- **Plan:** systemd services (server + LLM + ASR) with auto-restart, headless boot, locked-down
  image. Then the "black box / 99.9% uptime" framing is real.

---

## P2 — Compliance / integration (premium add-ons, only when sold) · Bucket B/C

- **PDPA Enterprise Audit Trail** — signed compliance cert + localised cryptographic logging
  proving zero retention (Add-on C). **Effort: ~1 week (Bucket B) when sold.**
- **Custom EMR / CMS webhook** — secure local API that pushes SOAP notes into the clinic's
  existing records software (Add-on C). **Effort: depends entirely on their EMR — Bucket C,
  quote per integration.**

---

*Keep this list in sync with `docs/MedicScribe_Pitch.md` and `docs/MedicScribe_Overview.md`:
when an item ships, the matching claim becomes safe to state in present tense.*
