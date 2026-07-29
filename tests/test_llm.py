import os

import pytest

from conftest import requires_llm
from fastcontext.agent.llm import LLM

pytestmark = [pytest.mark.requires_llm, requires_llm]


def _llm(**kwargs) -> LLM:
    return LLM(
        model=os.getenv("FC_MODEL") or os.getenv("MODEL"),
        api_key=os.getenv("FC_API_KEY") or os.getenv("API_KEY"),
        base_url=os.getenv("FC_BASE_URL") or os.getenv("BASE_URL"),
        **kwargs,
    )


async def test_llm():
    llm = _llm()
    messages = [
        {"role": "user", "content": "Hello, how are you?"},
    ]
    msg = await llm.acall(messages=messages, tools=None)

    assert msg.role == "assistant"
    assert msg.content


async def test_llm_tools():
    from fastcontext.agent.tool.read import ReadTool

    llm = _llm(temperature=0.0, max_tokens=1024)
    messages = [
        {"role": "system", "content": "You are a powerful AI agent."},
        {
            "role": "user",
            "content": "read file content from ./test_llm.py and ./README.md",
        },
    ]
    msg = await llm.acall(messages=messages, tools=[ReadTool().schema()])

    assert msg.tool_calls
    assert all(c.name == "Read" for c in msg.tool_calls)


async def test_llm_tools_result():
    llm = _llm(temperature=0.0, max_tokens=1024)
    messages = [
        {"role": "system", "content": "You are a powerful AI agent."},
        {"role": "user", "content": "please show me the current time"},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_0",
                    "function": {"arguments": '{"command": "date"}', "name": "bash"},
                    "type": "function",
                },
                {
                    "id": "call_1",
                    "function": {"arguments": '{"command": "date"}', "name": "bash"},
                    "type": "function",
                },
            ],
        },
        {
            "role": "tool",
            "content": "Thu Aug 21 17:42:44 CST 2025",
            "tool_call_id": "call_0",
        },
        {
            "role": "tool",
            "content": "Thu Aug 21 17:42:44 CST 2025",
            "tool_call_id": "call_1",
            "name": "bash",
        },
    ]
    msg = await llm.acall(messages=messages, tools=None)

    assert msg.role == "assistant"
    assert msg.content
