"""Offline tests for how LLM.acall dispatches.

Kept out of test_llm.py because that module is marked requires_llm as a whole,
and these must run without an endpoint.
"""

import pytest

from fastcontext.agent.llm import LLM


class _FakeUsage:
    def to_dict(self):
        return {"total_tokens": 1}


class _FakeMessage:
    role = "assistant"
    content = "ok"
    tool_calls = None


class _FakeChoice:
    finish_reason = "stop"
    message = _FakeMessage()


class _FakeResponse:
    usage = _FakeUsage()
    choices = [_FakeChoice()]


@pytest.mark.parametrize("model", ["claude-sonnet-5", "qwen3-4b", "gpt-5.4"])
async def test_every_model_goes_through_the_openai_client(model, monkeypatch):
    """No model name may be routed to a separate code path.

    A name containing "claude" used to import fastcontext.agent.llm_api, a
    module that has never existed in this repository, so every such call
    failed with ModuleNotFoundError wrapped in RequestyAPIError.
    """
    llm = LLM(model=model, api_key="unused", base_url="http://127.0.0.1:1/v1")

    seen = {}

    async def fake_create(**payload):
        seen["payload"] = payload
        return _FakeResponse()

    monkeypatch.setattr(llm.client.chat.completions, "create", fake_create)

    msg = await llm.acall(messages=[{"role": "user", "content": "hi"}], tools=None)

    assert msg.content == "ok"
    assert msg.model == model
    assert seen["payload"]["model"] == model
