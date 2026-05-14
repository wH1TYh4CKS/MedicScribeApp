# `llm/templates/` — Note templates

One folder per template. Each folder ships three files:

| File                | Purpose |
|---------------------|---------|
| `prompt.jinja`      | The Jinja prompt the LLM sees. Renders with `transcript`, `system_prompt`, `style_guide`, `few_shot` context. |
| `output_schema.json`| JSON Schema the LLM is forced to emit (vLLM guided decoding). Same schema is used to validate the LLM response. |
| `meta.yaml`         | Display name, description, version, list of top-level fields, language hints. |

## v1.0 templates

- **`soap_v1/`** — Subjective / Objective / Assessment / Plan. The only template enabled in v1.0.

## v1.1 templates (planned)

- `symptom_focus_v1/` — chief complaint + HPI + meds + allergies + plan.
- `paediatric_v1/` — adds growth/feeding fields.
- Whatever the doctor authors via the custom editor.

## Author a new template

1. `cp -r soap_v1/ <new_name>/`
2. Edit `prompt.jinja` — keep the JSON output instruction intact at the bottom.
3. Edit `output_schema.json` to define new fields.
4. Edit `meta.yaml`: bump `version`, set `name`, `description`, `fields`.
5. Restart the server, then either:
   - Set `notes.default_template=<new_name>` in `project.properties`, or
   - Pick it from the UI dropdown (v1.1).

## Versioning

Increment `meta.yaml::version` on any prompt or schema change. Old session notes still reference the version they were generated with — useful when reviewing why an old note looks different.
