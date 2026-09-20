# SOAP style guide

A SOAP note has four parts:

- **Subjective** — what the patient (and family) tells you. History of present illness (HPI), past medical history, social/family history, review of systems. Use the patient's own words for the chief complaint.
- **Objective** — what you measured or observed. Vitals (BP, HR, temp, SpO2, weight), physical exam findings, point-of-care investigations (urine dip, glucose, ECG).
- **Assessment** — the doctor's clinical reasoning. One or more problems, each with a differential and (where stated) an ICD-10 code.
- **Plan** — what happens next. Investigations ordered, prescriptions, referrals, lifestyle advice, follow-up timing.

Conventions for this scribe:
- One-line `chief_complaint` in the patient's own words.
- HPI written as a flowing paragraph, chronological.
- Vitals in a single line, comma-separated (`BP 140/90, HR 88, T 37.2, SpO2 98%`).
- Each medication is its own object; never bundle multiple drugs into one string.
- `assessment` is an array — list each active problem separately so it can be coded later.
- `plan` is an array — each entry is one actionable item (investigation, prescription, advice, follow-up).
