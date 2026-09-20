# MedicScribe — Privacy & PDPA Statement (Clinic Sign-off)

**Product:** MedicScribe — clinical consultation transcription + SOAP-note assistant
**Provider:** Sunkari Labs
**Regulation:** Malaysia Personal Data Protection Act 2010 (PDPA)
**Document version:** 1.1 — 2026-08-28

> **Status:** published as a design artifact. This described a specific deployment
> that is no longer running. It is not an offer of service, and MedicScribe is not
> a certified medical device.

This statement describes exactly what data MedicScribe handles, where it goes, and
how long it is kept. It is written for clinic owners and medical officers to review
and sign before using the system. Two deployment modes are covered separately because
their data-handling differs.

---

## 1. What the system does

A doctor records a consultation. MedicScribe converts the audio to text
(speech-to-text), then generates a structured SOAP note (Subjective / Objective /
Assessment / Plan) for the doctor to read, edit, and copy into their own records.

MedicScribe is an **assistant**. It does not store the medical record. The clinic's
existing record system remains the system of record.

---

## 2. Data lifecycle (what is kept, and for how long)

| Data | Where it lives | Retention | How it is destroyed |
|------|----------------|-----------|---------------------|
| Consultation audio | A temporary file on the MedicScribe server | **Deleted the moment recording stops** (before the note is even generated) | File unlinked from disk; a startup sweeper removes any stray file older than 1 hour as a safety net |
| Transcript (the text) | Server memory (RAM) only | Held only during the few seconds of note generation | Memory explicitly cleared when the session ends |
| SOAP note | Sent straight to the doctor's screen | **Never written to the server** | Exists only in the doctor's browser and clipboard; gone when the page is closed |

**Net result: after a consultation ends, the MedicScribe server retains zero
consultation data.** There is no database, no audio archive, no transcript store, and
no note store. This has been verified by inspection of the running system: the audio
directory is empty after use, and neither the application log nor the language-model
log contains any patient or clinical text (logs record only session identifiers,
byte counts, and durations).

---

## 3. Where the data travels

### Mode A — On-site rental (production deployment in your clinic)
- A dedicated MedicScribe computer sits **inside the clinic on the clinic's own
  network (LAN)**.
- Audio, transcript, and note **never leave the clinic premises**. No internet, no
  cloud, no third-party service touches the data.
- This is the everyday deployment for clinics that want no audio to leave the building.

### Mode B — Remote access (before or instead of an on-site box)
- The clinic uses MedicScribe over the internet, connecting to a Sunkari Labs
  server through an encrypted (HTTPS) link.
- In this mode, audio is transmitted over the internet and passes through an
  internet routing provider (Cloudflare) before reaching the Sunkari Labs server.
  The same "delete on stop / store nothing" rules apply at the server.
- Real consultations **are permitted** here provided the clinic obtains patient
  consent to record (see §4). Clinics that prefer no audio leaving the premises at
  all should use Mode A, which removes this exposure entirely.

---

## 4. PDPA alignment

- **Purpose limitation:** Data is used solely to produce the note the doctor
  requested. No secondary use, no analytics on clinical content, no model training
  on consultations.
- **Data minimisation / storage limitation:** Nothing is retained after the session.
  There is no standing collection of personal data to secure, breach, or subject-access.
- **Security:** Transport is encrypted (HTTPS/TLS). Production runs on an isolated
  clinic LAN. The language model runs locally on the MedicScribe machine
  (`localhost`), so transcripts are not sent to any external AI provider.
- **Disclosure to third parties:** None in production (Mode A). In remote-access
  (Mode B), only the internet transport provider routes the encrypted connection; it
  is not a data recipient and stores no consultation content on Sunkari Labs' behalf.
- **Patient consent:** The clinic, as data controller, remains responsible for
  obtaining patient consent to record the consultation, per PDPA and MMC guidance.
  MedicScribe provides the recording tool; the consent conversation is the clinic's.
- **Data controller / processor:** The **clinic is the data controller**. In remote
  mode (Mode B), **Sunkari Labs acts as a transient data processor** that retains
  nothing. In Mode A, data does not leave the controller's premises at all.

---

## 5. What this means for the clinic

- You do not need to manage a MedicScribe data store — there isn't one.
- Real consultations are supported in either mode; use Mode A if you want no audio
  ever leaving the clinic.
- You obtain patient consent to record; the clinic remains the data controller.
- You retain full control of the actual medical record in your existing system.

---

## 6. Sign-off

By signing, the clinic confirms it has read this statement, understands the remote-mode
data-transit caveat, and accepts responsibility for obtaining patient consent to recording.

| Field | Entry |
|-------|-------|
| Clinic name | __________________________ |
| Authorised signatory | __________________________ |
| Designation | __________________________ |
| Deployment mode | ☐ On-site box (Mode A)  ☐ Remote access (Mode B) |
| Date | __________________________ |
| Signature | __________________________ |

*Questions on data handling: Sunkari Labs.*
