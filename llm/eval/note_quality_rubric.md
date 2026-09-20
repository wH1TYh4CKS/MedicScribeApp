# Note quality rubric (Phase 5)

Score each generated note on these axes (0–2 each, max 14):

| Axis                 | 0 = fail                          | 1 = partial                                  | 2 = pass                                       |
|----------------------|-----------------------------------|----------------------------------------------|------------------------------------------------|
| Faithful to transcript | Hallucinated symptoms / meds      | Minor omission                               | Every fact traceable to transcript             |
| SOAP completeness    | Missing major section             | One section thin                             | All four sections present and adequate         |
| Clinical English     | Wrong clinical terminology        | Awkward phrasing                             | Clean, EMR-portable English                    |
| Med extraction       | Missed or wrong dose / frequency  | One field off (e.g. duration)                | Name + dose + frequency + duration all correct |
| Multilingual handling| Translates patient quotes         | Inconsistent quote handling                  | Quotes preserved, clinical fields in English   |
| ICD-10               | Wrong code                        | Generic code where specific exists           | Correct, specific code                         |
| PII redaction        | Names / IDs leaked                | Partial redaction                            | All PII replaced with `[REDACTED]`             |

Pass threshold: **≥ 11/14** for the demo.

Run on the `manglish_corpus/` set; collect average per axis and per template version.
