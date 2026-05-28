import json

import httpx
import pytest

from medicscribe_server.llm_client.base import LLMError
from medicscribe_server.llm_client.openai_compat import OpenAICompatClient

SCHEMA = {"type": "object", "required": ["chief_complaint"],
          "properties": {"chief_complaint": {"type": "string"}}}


def _client(handler):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url="http://test")
    return OpenAICompatClient(
        endpoint="http://test/v1", model="qwen", params={"temperature": 0.2, "max_tokens": 800},
        timeout=10, guided=True, http_client=http,
    )


def test_builds_request_and_parses_content():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        content = json.dumps({"chief_complaint": "Fever for 2 days."})
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    note = _client(handler).complete_json("the prompt", SCHEMA)
    assert note == {"chief_complaint": "Fever for 2 days."}
    assert seen["url"].endswith("/v1/chat/completions")
    assert seen["body"]["model"] == "qwen"
    assert seen["body"]["messages"][0]["role"] == "user"
    assert seen["body"]["messages"][0]["content"] == "the prompt"
    assert seen["body"]["guided_json"] == SCHEMA
    assert seen["body"]["temperature"] == 0.2


def test_http_error_raises_llmerror():
    def handler(request):
        return httpx.Response(500, text="boom")
    with pytest.raises(LLMError):
        _client(handler).complete_json("p", SCHEMA)


def test_non_json_content_raises_llmerror():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
    with pytest.raises(LLMError):
        _client(handler).complete_json("p", SCHEMA)
