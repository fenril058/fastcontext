"""Offline tests for how LLM.acall dispatches.

Kept out of test_llm.py because that module is marked requires_llm as a whole,
and these must run without an endpoint.
"""

import pytest

from fastcontext.agent.llm import LLM, LLMAPIError


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
    failed with ModuleNotFoundError wrapped in LLMAPIError.
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


async def _payload_for(model: str, monkeypatch) -> dict:
    llm = LLM(model=model, api_key="unused", base_url="http://127.0.0.1:1/v1")
    seen = {}

    async def fake_create(**payload):
        seen.update(payload)
        return _FakeResponse()

    monkeypatch.setattr(llm.client.chat.completions, "create", fake_create)
    await llm.acall(messages=[{"role": "user", "content": "hi"}], tools=None)
    return seen


async def test_a_model_name_no_longer_decides_extra_body(monkeypatch):
    """`if "qwen" in self.model` sent Qwen serving options to anything so named."""
    monkeypatch.delenv("FC_EXTRA_BODY", raising=False)

    payload = await _payload_for("qwen3-4b", monkeypatch)

    assert "extra_body" not in payload


async def test_extra_body_is_taken_from_the_environment(monkeypatch):
    monkeypatch.setenv("FC_EXTRA_BODY", '{"top_k": 20, "chat_template_kwargs": {"enable_thinking": false}}')

    payload = await _payload_for("anything", monkeypatch)

    assert payload["extra_body"] == {"top_k": 20, "chat_template_kwargs": {"enable_thinking": False}}


@pytest.mark.parametrize("value", ["not json", "[1, 2]", '"a string"'])
async def test_malformed_extra_body_is_reported_clearly(value, monkeypatch):
    monkeypatch.setenv("FC_EXTRA_BODY", value)
    llm = LLM(model="anything", api_key="unused", base_url="http://127.0.0.1:1/v1")

    with pytest.raises(LLMAPIError, match="FC_EXTRA_BODY"):
        await llm.acall(messages=[{"role": "user", "content": "hi"}], tools=None)
