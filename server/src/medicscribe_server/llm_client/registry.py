from __future__ import annotations

import os
from pathlib import Path

import yaml

from medicscribe_server.llm_client.base import LLMClient
from medicscribe_server.llm_client.openai_compat import OpenAICompatClient
from medicscribe_server.llm_client.stub import StubLLMClient


def load_note_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_llm_client(config_path: Path) -> LLMClient:
    cfg = load_note_config(config_path)
    engine = cfg.get("engine")
    if engine == "stub":
        return StubLLMClient()
    if engine in ("vllm", "openai-compat", "tgi", "llama-cpp"):
        # Keep secrets out of the committed yaml: fall back to env var when
        # api_key is null. llmw's bearer token lives in $MEDICSCRIBE_NOTE_API_KEY.
        api_key = cfg.get("api_key") or os.environ.get("MEDICSCRIBE_NOTE_API_KEY")
        return OpenAICompatClient(
            endpoint=cfg["endpoint"],
            model=cfg["model_id"],
            params=cfg.get("params", {}),
            timeout=float(cfg.get("timeout_seconds", 60)),
            api_key=api_key,
            guided=bool(cfg.get("guided_decoding", {}).get("enabled", True)),
            # When set, return ``{text_field: raw_content}`` instead of parsing
            # JSON. Use with models trained to emit prose (e.g. sum-small).
            text_field=cfg.get("response_text_field"),
        )
    raise ValueError(f"unknown note-gen engine: {engine}")
