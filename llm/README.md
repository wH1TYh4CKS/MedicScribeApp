# `llm/` — Prompts, templates, model registry, eval corpus

The "thought layer" of MedicScribe. Everything in here is **content + config**, not executable code. The server reads from this folder at runtime; editing a template or swapping a model never requires opening `server/`.

## Layout

```
llm/
├── README.md                    this file
├── models/                      model registry — server reads at boot
│   ├── asr.yaml                 which ASR engine + model + params
│   ├── note_llm.yaml            which LLM serving stack + model + sampling
│   └── README.md
├── prompts/                     reusable prompt fragments (shared across templates)
│   ├── system_doctor_scribe.jinja      base system prompt
│   ├── style_guides/                   markdown reference docs the prompt embeds
│   │   ├── soap.md
│   │   └── manglish_rules.md
│   └── few_shot/                       JSON examples
│       ├── soap_example_en.json
│       └── soap_example_manglish.json
├── templates/                   one folder per note template
│   ├── README.md
│   └── soap_v1/                 ← v1.0 ships only this template
│       ├── prompt.jinja         assembled Jinja prompt (renders with: transcript, fragments)
│       ├── output_schema.json   JSON Schema for guided decoding
│       └── meta.yaml            { name, description, version, fields }
├── custom/                      doctor-authored templates (v1.1 — UI editor lands then)
│   ├── .gitkeep
│   └── _example/                contract reference for custom template authors
│       ├── prompt.jinja
│       ├── output_schema.json
│       └── meta.yaml
└── eval/                        multilingual eval set (Phase 5)
    ├── manglish_corpus/
    └── note_quality_rubric.md
```

## Authoring a new note template

1. Copy `templates/soap_v1/` to `templates/<your_template_name>/`.
2. Edit `prompt.jinja` — the renderer passes `{{ transcript }}`, `{{ system_prompt }}`, `{{ few_shot }}`, `{{ style_guide }}`.
3. Edit `output_schema.json` — define the JSON shape the LLM must emit. The server uses this for guided decoding so the response is always parseable.
4. Edit `meta.yaml` — bump `version`, set `fields` to the top-level keys in your schema.
5. Restart the server. The template is now selectable in the UI (v1.1) or as the default (set `notes.default_template` in `project.properties`).

## Swapping models

See `models/README.md`. TL;DR: edit one yaml line, restart.

## Why this lives outside `server/`

- A doctor or prompt engineer can fork a template without git-cloning the server code.
- Templates can be hot-reloaded without rebuilding a Docker image.
- `git diff llm/` cleanly shows prompt changes — easy to review prompt regressions.
- Eval corpus (`eval/`) sits next to the prompts that produced it — one place for prompt science.
