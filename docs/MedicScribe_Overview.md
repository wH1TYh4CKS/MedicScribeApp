<p style="letter-spacing:2px"><b>MEDICAL TRANSCRIPTION AI</b></p>

# MedicScribe

### A private medical scribe for Malaysian clinics
*by Sunkarilabs*

**Data Sovereignty · Zero-Cloud Liability · Specialized Medical Intelligence**

**What it is:** a tool that listens to your consultation and writes a structured clinical note for you to review, edit, and export — so you spend the visit with the patient, not the keyboard.

**Status:** working and field-tested today. The screenshots in this document are from the live app.

**The promise:** your patients' data is **sovereign** — it stays on hardware you control and never touches the cloud. No third party ever holds, sees, or could leak it.

**How it is delivered:** a sealed, headless "black box" AI server that runs on its own — locked down, with nothing to manage and nothing to tinker with.

---

## 1. What it does today

You press one button at the start of the consultation and one button at the end. About a few seconds after you stop, a clean SOAP note appears on your screen. You read it, fix anything you want, and share or export it.

The app is built on speech-recognition models tuned for Malaysian multilingual consultations — it handles English, Malay, Mandarin and Tamil, plus local **dialects and everyday slang (Manglish)**, including switching between them in the same sentence — and still produces an **English** note.

| ![Start](assets/sm_StartScreen1.jpeg) | ![Recording](assets/sm_StopScreen.jpeg) | ![Note](assets/sm_SOAPnote.jpeg) | ![Privacy](assets/sm_Privacynote.jpeg) |
|---|---|---|---|
| **1. Start** — one button; banner reminds you the data is private, not the cloud. | **2. Recording** — the button becomes Stop. Nothing else to manage. | **3. The note** — a ready SOAP note you can edit and Share. | **4. Privacy trail** — proof of exactly what happened to the data. |

In the real example above, the system captured the patient's complaint and a detailed medication plan from a two-minute conversation, and the note was ready a few seconds after Stop. The privacy trail shows the audio was **deleted on the server**, the note is **export-only — never stored**, and everything is **wiped when you tap Done**.

---

## 2. How it works (in plain terms)

The phone or tablet does **not** do the thinking. It only records your voice and shows you the result. The actual work is done by two AI models running on a separate computer — the **server**:

1. **You record** — the app captures the consultation audio.
2. **Speech → text** — the first model turns the spoken consultation into written text, translating any mix of languages into English along the way.
3. **Text → note** — the second model reads that text and organises it into a structured SOAP note.
4. **You review** — the note returns to your screen to edit, share, and export.

Two buttons for you. Two models doing the work behind the scenes.

---

## 3. Data Sovereignty — why it never touches the cloud

Most medical scribes on the market send the recording to a company's servers on the internet. For patient data, that is a permanent liability. MedicScribe runs on **one dedicated machine you control** — either a private Sunkarilabs server (evaluation) or a sealed server installed in your own clinic.

- **Data sovereignty:** the audio and the note live only on your hardware. No cloud account, no foreign data centre, no vendor holding your records.
- **Zero-cloud liability:** nothing leaves the building, so there is no cloud breach surface to be liable for. This can be guaranteed contractually (see the PDPA Audit Trail add-on).
- **Offline by design:** a clinic server keeps working even if your internet is down.
- **No lock-in:** built on open-source models — no per-record cloud fees, no subscription you can't leave.

---

## 4. Why the hardware matters (and why a bigger one costs more)

The AI models run on a **graphics card (GPU)** inside the server. This single component decides how good and how fast the notes are:

- A GPU has a **fixed amount of working memory** — think of it as a fixed-size desk. Each model must fit entirely on that desk to run **at all**. If a model is bigger than the desk, it will not start.
- A **smarter, more accurate model is also a bigger model**, so it needs a **bigger desk** (more GPU memory).
- **More doctors recording at once** means more jobs sharing the desk — more room needed.

This is why the on-site standard uses a **24 GB GPU** for 1–2 doctors, and the multi-doctor tier uses a multi-GPU architecture for 3–5 doctors running in parallel.

> **Higher accuracy or more doctors → a bigger GPU → higher hardware cost.** Hardware is the lower-cost lever; bespoke model work is the premium one. We size the hardware to the clinic.

---

## 5. A sealed "black box" — reliability, SLA & uptime

The server is delivered **headless** — no screen, no desktop, nothing on it to open or change. Everything runs automatically inside the box. This is deliberate:

- **All the graphics-card memory goes to the models.** A screen or desktop on the server would quietly use part of that same memory; on a smaller server that can be enough to tip it over and stop a note from running. Headless keeps every bit of the card free for making notes.
- **Full, exclusive control of the card.** Nothing else runs, so no stray program competes for memory and interrupts a note.
- **No tinkering, no leaks.** Nothing for anyone to fiddle with, mis-configure, or copy data out of. A sealed system is a safe system.
- **Engineered for uptime.** Because the system is locked down with no software clutter, it needs virtually zero manual maintenance — built for **99.9% uptime**.

**If it ever does fail, you lose nothing.** Notes are export-only and nothing is half-saved, so there is no data to lose — you simply resume the moment the server is back.

**Support & SLA:** your monthly licence is a direct line to the engineer who built the system — not a call-centre queue. Issues are attended to personally, weekends included. For on-site clinics, an optional **Cold-Swap hardware SLA** guarantees a physical replacement server within 24 hours (see add-ons).

---

## 6. Packages & pricing

Three tiers, from a low-commitment pilot to a multi-doctor clinic deployment. All figures are in Malaysian Ringgit and confirmed against the final specification at quotation.

| Tier | What is included | Rate (MYR) |
|---|---|---|
| **1. Private Cloud Evaluation** | A secure, encrypted private link to a dedicated Sunkarilabs server. Strictly a **single-doctor pilot, 3 months maximum** — to prove the value before committing to on-site hardware. | **RM 1,500 / month** + RM 3,000 one-time setup |
| **2. Local On-Site "Black Box"** — *RECOMMENDED* | A sealed, headless AI server **physically installed inside your clinic**. 100% offline — zero internet or cloud reliance. Supports **1–2 doctors**. The enterprise standard. | **RM 15,000** hardware (one-time) + RM 5,000 installation + RM 650 / month licence & SLA |
| **3. Multi-Doctor Clinic** | A high-spec **multi-GPU server** built to run heavy parallel inference for **3–5 doctors simultaneously**, fully on-site and offline. | **RM 28,000** hardware (one-time) + RM 8,000 installation + RM 1,200 / month licence & SLA |

*The monthly licence & SLA is your retainer: priority access to the engineer who built the system, software updates, and the reliability guarantee — not a charge for "updates" alone.*

---

## 7. Premium add-ons

These extend the platform with specialised execution that generic, mass-market AI tools cannot provide.

### A · Specialty Vocabulary Tuning — Specialized Medical Intelligence

Off-the-shelf AI models fail at specific clinical jargon. We custom-tune the underlying language models for your medical branch's focus. *Example — Aesthetic & Dermatology Pack:* custom weights trained to recognise laser types (Picosecond, Q-Switched Nd:YAG), conditions (Melasma, Post-Inflammatory Hyperpigmentation), and premium skincare brand names.

**From RM 12,000 one-time, per specialised model.**

### B · Premium Hardware & Hardware SLA

**Black-Box + Mic Bundle:** a medical-grade, highly sensitive directional wireless microphone paired with a custom-anodised, silent mini-ITX server chassis — sleek on a clinic counter, and it eliminates tablet-microphone distortion.
**RM 3,500 per consultation room.**

**Cold-Swap Guarantee (Hardware SLA):** if an on-site server hits a hardware fault, Sunkarilabs physically delivers and swaps a temporary replacement server within **24 hours, weekends included**.
**+ RM 250 / month on the base maintenance tier.**

### C · Compliance & Custom Integration

**PDPA Enterprise Audit Trail:** a signed compliance certificate and a localised cryptographic logging system that proves no patient audio or text was retained on-site or leaked.
**Included in Tier 2 & 3 · RM 2,000 one-time for Tier 1.**

**Custom EMR / CMS Webhook Integration:** a secure local API endpoint that pushes generated SOAP notes straight into your clinic's existing medical-records software with one click.
**From RM 5,000, quoted on your software's complexity.**

---

## 8. iPad and Android — which device

The app can be supplied on **both an iPad and an Android tablet**. They differ only in how soon each is ready:

- **Android:** ready now — this is the field-tested app in the screenshots.
- **iPad / iPhone (iOS):** needs additional development time, because Apple's App Store rules are strict. The practical route is to run MedicScribe as a **secure local web app (HTTPS)** served by your own clinic server and opened in the iPad's browser — no App Store needed.

For the iPad/iPhone route to be trusted and encrypted, each device needs a small **security certificate ("CA") installed once**. After that one-time step it behaves like a normal app, and stays **fully local — still no cloud**. The iPad is only the *recorder*; the AI work happens on the server either way. App layout changes and the iOS build are delivered as a quoted app-design upgrade.

---

## 9. Privacy, compliance & PDPA

- **No cloud.** Audio and notes stay on hardware you control — full data sovereignty.
- **Sealed server.** Headless and locked down — nothing to tinker with, nothing to leak.
- **Zero data retention** — the server only runs the models and transcribes; nothing is kept. Guaranteed by contract, provable with the PDPA Enterprise Audit Trail.
- **Audio deleted** on the server right after the note is generated.
- **Notes are export-only** — never stored on the server.
- **Everything wiped** when you tap Done, with an on-screen audit trail each time.
- **No data loss** if the server ever fails — nothing is half-saved; just resume.
- **Built for Malaysia's PDPA 2010** — open-source models, no lock-in, no per-record cloud fees.

---

## Get in touch

**Surenther Saravanan** — Sunkarilabs
Phone / WhatsApp: **014-635 7916**
Email: **surenthersaravanan@gmail.com**

---

*MedicScribe by Sunkarilabs — Data Sovereignty · Zero-Cloud Liability · Specialized Medical Intelligence.*
