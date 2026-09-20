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

    def healthy(self) -> bool:
        """Ping the LLM server's /models with a short timeout. Result cached for
        ~5s so a page full of pollers can't hammer the backend."""
        import time

        now = time.monotonic()
        cached = getattr(self, "_health_cache", None)
        if cached is not None and now - cached[0] < 5.0:
            return cached[1]
        try:
            ok = self._http.get(f"{self._endpoint}/models", timeout=2.0).status_code == 200
        except httpx.HTTPError:
            ok = False
        self._health_cache = (now, ok)
        return ok

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
        # Qwen3.6 (the note model) is a thinking model; disable reasoning so `content`
        # is the bare SOAP note and the token budget isn't eaten by <think> blocks.
        # Harmless to OpenAI-compat servers that ignore the field.
        body["chat_template_kwargs"] = {"enable_thinking": False}
        # Greedy decoding (temperature 0) with no penalty degenerates on long,
        # noisy transcripts: a 22-min code-switched consult sent Qwen3.8-27B into
        # an endless "- Patient reports no known specific steroid <ordinal> care
        # effect" loop after 11 good bullets, eating the whole token budget before
        # it reached O:/A:/P:. Forward penalties when the yaml sets them; omitted
        # keys keep the server's defaults, so behaviour is unchanged unless configured.
        for key in ("repetition_penalty", "frequency_penalty", "presence_penalty"):
            if key in self._params:
                body[key] = self._params[key]
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
