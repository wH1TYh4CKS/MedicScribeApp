# Manglish + Malaysian multilingual handling

The transcript is from a Malaysian clinic. Expect Manglish, code-switching, and loanwords.

Rules:

1. **Preserve original language for direct patient quotes.** If the patient says *"Doctor, my anak ada batuk for three days lah"*, keep it as-is in the HPI; do not translate.
2. **Translate clinical content to English** in `assessment`, `plan`, `medications`. Other clinicians may not read all four languages.
3. **Common Manglish discourse particles can be dropped** when they carry no clinical meaning: *lah, lor, mah, leh, hor, meh, ah*. Keep them only inside direct quotes.
4. **Loanwords / mixed terms — keep as written**, with a brief English gloss in brackets if non-obvious. Examples:
   - *demam* → fever
   - *sakit kepala* → headache
   - *batuk berkahak* → productive cough
   - *pening* → dizziness / lightheadedness
   - *kencing manis* → diabetes mellitus
   - *darah tinggi* → hypertension
   - *angin* → flatulence / "wind" complaint
   - *panas* → fever / hot
   - *muntah* → vomiting
   - *cirit-birit* → diarrhoea
   - *hujung minggu* → weekend
   - *sebulan* → one month
5. **Numbers and durations**: convert spelled-out durations to a short form (`3/7` for 3 days, `2/52` for 2 weeks, `1/12` for 1 month). Keep exact numbers stated by the patient — do not round or approximate.
6. **Names and IDs are PII** — replace with `[REDACTED]` if they appear.
7. **Tamil and Mandarin medical terms**: same rule — preserve in quotes, translate in clinical fields.
8. **Doctor and patient turns** are not always labelled in the transcript. Infer from context: directives ("take this twice a day", "open your mouth") are doctor; symptom statements ("I feel...", *"saya rasa..."*) are patient.
