from __future__ import annotations

import logging

import jsonschema

from medicscribe_server.llm_client.base import LLMClient, LLMError
from medicscribe_server.notes.template import NoteTemplate

logger = logging.getLogger(__name__)


class NoteGenerationError(Exception):
    """Note generation failed after all retries."""


class NoteGenerator:
    """Render prompt -> call LLM -> validate against schema, with bounded retries.

    Sync (wrapped in asyncio.to_thread by the WS session). Never logs transcript
    or note content (PHI) — only attempt counts and error types.
    """

    def __init__(self, client: LLMClient, template: NoteTemplate, max_retries: int = 3) -> None:
        self._client = client
        self._template = template
        self._max_retries = max_retries

    def close(self) -> None:
        """Release the underlying LLM client's resources. Called on app shutdown."""
        self._client.close()

    def generate(self, transcript: str) -> dict:
        prompt, schema = self._template.render(transcript)
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                note = self._client.complete_json(prompt, schema)
                jsonschema.validate(note, schema)
                return note
            except (LLMError, jsonschema.ValidationError) as exc:
                last_error = exc
                logger.warning("note-gen attempt %d/%d failed: %s",
                               attempt, self._max_retries, type(exc).__name__)
        raise NoteGenerationError(
            f"note generation failed after {self._max_retries} attempts"
        ) from last_error
