from __future__ import annotations

import json

import httpx

from medicscribe_server.llm_client.base import LLMClient, LLMError


class OpenAICompatClient(LLMClient):
    """Talks to any OpenAI-compatible server (vLLM, llama-cpp-python, TGI…).

    Two response modes:
      - **JSON mode (default):** content is parsed as JSON. Pair with `guided=True`
        on vLLM (uses `guided_json`) for schema-constrained output.
      - **Text-wrapper mode (`text_field` set):** content is taken as raw text
        and wrapped as ``{text_field: content}``. Use for models trained to emit
        free-form text (e.g. omi-health/sum-small emits S:/O:/A:/P:).
    """

    def __init__(
        self,
        endpoint: str,
        model: str,
        params: dict,
        timeout: float = 60.0,
        api_key: str | None = None,
        guided: bool = True,
        http_client: httpx.Client | None = None,
        text_field: str | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._params = params or {}
        # `guided_json` is meaningless when we're not asking for JSON output.
        self._guided = guided and text_field is None
        self._text_field = text_field
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._owns_http = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout, headers=headers)

    def close(self) -> None:
        """Release the connection pool. Only closes a client we created, never
        an injected one (the caller owns that). Call on app shutdown."""
        if self._owns_http:
            self._http.close()

    def complete_json(self, prompt: str, schema: dict) -> dict:
        body: dict = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._params.get("temperature", 0.2),
            "top_p": self._params.get("top_p", 0.9),
            "max_tokens": self._params.get("max_tokens", 800),
        }
        if self._guided:
            body["guided_json"] = schema
        try:
            resp = self._http.post(f"{self._endpoint}/chat/completions", json=body)
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        if self._text_field is not None:
            return {self._text_field: content}
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM returned non-JSON content: {exc}") from exc
