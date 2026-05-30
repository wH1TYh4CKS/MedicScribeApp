from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(Exception):
    """Transport/protocol failure talking to the note-generation LLM."""


class LLMClient(ABC):
    """Sync LLM transport. Wrapped in asyncio.to_thread by the WS session."""

    @abstractmethod
    def complete_json(self, prompt: str, schema: dict) -> dict:
        """Send `prompt`, return a parsed JSON object constrained to `schema`.

        Raises LLMError on transport failure or unparseable output.
        """
        raise NotImplementedError

    def close(self) -> None:  # noqa: B027  # optional hook, default no-op
        """Release any held resources (connection pools, etc.). No-op by default;
        override if the transport owns something. Called on app shutdown."""
