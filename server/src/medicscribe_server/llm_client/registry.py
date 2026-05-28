from __future__ import annotations

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
    if engine in ("vllm", "openai-compat", "tgi"):
        return OpenAICompatClient(
            endpoint=cfg["endpoint"],
            model=cfg["model_id"],
            params=cfg.get("params", {}),
            timeout=float(cfg.get("timeout_seconds", 60)),
            api_key=cfg.get("api_key"),
            guided=bool(cfg.get("guided_decoding", {}).get("enabled", True)),
        )
    raise ValueError(f"unknown note-gen engine: {engine}")
