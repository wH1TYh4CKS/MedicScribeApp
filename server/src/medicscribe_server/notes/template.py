from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import jinja2


@dataclass
class NoteTemplate:
    """A note template = a Jinja prompt + a JSON Schema + shared prompt parts.

    Layout under `llm_root`:
      templates/<name>/prompt.jinja
      templates/<name>/output_schema.json
      prompts/system_doctor_scribe.jinja
      prompts/style_guides/soap.md
      prompts/few_shot/*.json   (each: {"transcript": str, "note_json": obj|str})
    """

    name: str
    schema: dict
    _prompt: jinja2.Template
    _system: str
    _style_guide: str
    _few_shot: list[dict]

    @classmethod
    def load(cls, name: str, llm_root: Path) -> "NoteTemplate":
        llm_root = Path(llm_root)
        tdir = llm_root / "templates" / name
        schema = json.loads((tdir / "output_schema.json").read_text(encoding="utf-8"))
        prompt = jinja2.Template((tdir / "prompt.jinja").read_text(encoding="utf-8"))
        system = (llm_root / "prompts" / "system_doctor_scribe.jinja").read_text(encoding="utf-8")
        style = (llm_root / "prompts" / "style_guides" / "soap.md").read_text(encoding="utf-8")

        few_shot: list[dict] = []
        fs_dir = llm_root / "prompts" / "few_shot"
        for fp in sorted(fs_dir.glob("*.json")):
            ex = json.loads(fp.read_text(encoding="utf-8"))
            note_json = ex.get("note_json", "")
            if not isinstance(note_json, str):
                note_json = json.dumps(note_json, ensure_ascii=False, indent=2)
            few_shot.append({"transcript": ex.get("transcript", ""), "note_json": note_json})

        return cls(name=name, schema=schema, _prompt=prompt, _system=system,
                   _style_guide=style, _few_shot=few_shot)

    def render(self, transcript: str) -> tuple[str, dict]:
        prompt = self._prompt.render(
            system_prompt=self._system,
            style_guide=self._style_guide,
            few_shot=self._few_shot,
            transcript=transcript,
            output_schema_json=json.dumps(self.schema, ensure_ascii=False, indent=2),
        )
        # Shallow copy so a caller can't mutate the cached schema between renders.
        return prompt, dict(self.schema)
