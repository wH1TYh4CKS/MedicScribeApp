from __future__ import annotations

import os
from pathlib import Path

import yaml

from medicscribe_server.llm_client.base import LLMClient
from medicscribe_server.llm_client.openai_compat import OpenAICompatClient
from medicscribe_server.llm_client.stub import StubLLMClient


def load_note_config(config_path: Path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _env_override(cfg: dict, key: str, env_var: str):
    """Environment wins over the committed yaml.

    The yaml records the GPU deployment this was tuned on. A container, a
    laptop or CI points somewhere else entirely without editing a tracked
    file — and secrets never land in the yaml at all.
    """
    return os.environ.get(env_var) or cfg.get(key)


def build_llm_client(config_path: Path) -> LLMClient:
    cfg = load_note_config(config_path)
    engine = _env_override(cfg, "engine", "MEDICSCRIBE_NOTE_ENGINE")
    if engine == "stub":
        return StubLLMClient()
    if engine in ("vllm", "openai-compat", "tgi", "llama-cpp"):
        api_key = _env_override(cfg, "api_key", "MEDICSCRIBE_NOTE_API_KEY")
        return OpenAICompatClient(
            endpoint=_env_override(cfg, "endpoint", "MEDICSCRIBE_NOTE_ENDPOINT"),
            model=_env_override(cfg, "model_id", "MEDICSCRIBE_NOTE_MODEL"),
            params=cfg.get("params", {}),
            timeout=float(cfg.get("timeout_seconds", 60)),
            api_key=api_key,
            guided=bool(cfg.get("guided_decoding", {}).get("enabled", True)),
            # When set, return ``{text_field: raw_content}`` instead of parsing
            # JSON. Use with models trained to emit prose (e.g. sum-small).
            text_field=cfg.get("response_text_field"),
        )
    raise ValueError(f"unknown note-gen engine: {engine}")
