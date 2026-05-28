from __future__ import annotations

import copy

from medicscribe_server.llm_client.base import LLMClient, LLMError

_DEFAULT_NOTE = {
    "chief_complaint": "Headache since this morning.",
    "subjective": {"history_of_present_illness": "Patient reports headache since morning, no trauma."},
    "objective": {},
    "assessment": [{"problem": "Tension headache"}],
    "plan": [{"action": "Paracetamol 500mg PRN; review if persists."}],
    "medications": [{"name": "Paracetamol", "dose": "500mg", "frequency": "PRN"}],
    "allergies": [],
    "follow_up": "Return if symptoms worsen.",
}


class StubLLMClient(LLMClient):
    """In-memory client for tests and pipeline dev without a running vLLM.

    `fail_times` makes the first N calls raise LLMError (to exercise retries).
    """

    def __init__(self, response: dict | None = None, fail_times: int = 0) -> None:
        self._response = response if response is not None else _DEFAULT_NOTE
        self._fail_times = fail_times
        self.calls = 0

    def complete_json(self, prompt: str, schema: dict) -> dict:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise LLMError(f"stub forced failure {self.calls}")
        # Deep copy: callers may mutate the note; never corrupt the shared default.
        return copy.deepcopy(self._response)
