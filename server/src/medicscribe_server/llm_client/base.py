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

    def healthy(self) -> bool:
        """Cheap liveness probe of the underlying LLM backend. Default True
        (in-process/stub clients are always up); HTTP clients override to ping
        the server. Used by the /health/ready readiness endpoint."""
        return True

    def close(self) -> None:  # noqa: B027  # optional hook, default no-op
        """Release any held resources (connection pools, etc.). No-op by default;
        override if the transport owns something. Called on app shutdown."""
