import asyncio
import json
import time

import pytest

from fastcontext.agent.llm import FunctionCall, Message
from fastcontext.agent.tool import ToolSet
from fastcontext.agent.tool.read import ReadTool
from fastcontext.agent.tool.tool import Tool


async def test_toolset_schema_list():
    toolset = ToolSet(tools=[ReadTool()], work_dir=".")
    schema_list = toolset.schema_list()

    assert len(schema_list) == 1
    assert schema_list[0]["function"]["name"] == "Read"


async def test_toolset_call_returns_one_message_per_tool_call(tmp_path):
    first = tmp_path / "first.md"
    first.write_text("sentinel-alpha\n", encoding="utf-8")
    second = tmp_path / "second.md"
    second.write_text("sentinel-beta\n", encoding="utf-8")

    toolset = ToolSet(tools=[ReadTool()], work_dir=str(tmp_path))
    tool_call_msg = Message(
        role="assistant",
        content=None,
        tool_call_id="call_1",
        tool_calls=[
            FunctionCall(id="call_1_1", name="Read", arguments=json.dumps({"path": str(first)})),
            FunctionCall(id="call_1_2", name="Read", arguments=json.dumps({"path": str(second)})),
        ],
    )

    messages = await toolset.call(tool_call_msg)

    assert [m.tool_call_id for m in messages] == ["call_1_1", "call_1_2"]
    assert all(m.role == "tool" for m in messages)
    assert "sentinel-alpha" in messages[0].content
    assert "sentinel-beta" in messages[1].content


async def test_toolset_surfaces_tool_failure(tmp_path):
    missing = tmp_path / "missing.md"
    toolset = ToolSet(tools=[ReadTool()], work_dir=str(tmp_path))
    tool_call_msg = Message(
        role="assistant",
        content=None,
        tool_call_id="call_1",
        tool_calls=[FunctionCall(id="call_1_1", name="Read", arguments=json.dumps({"path": str(missing)}))],
    )

    messages = await toolset.call(tool_call_msg)

    assert len(messages) == 1
    # Assert on the error envelope and the offending path rather than on the
    # exact prose, which ReadTool is free to reword.
    assert "<system-reminder>" in messages[0].content
    assert str(missing) in messages[0].content


async def test_toolset_reports_unknown_tool():
    toolset = ToolSet(tools=[ReadTool()], work_dir=".")
    tool_call_msg = Message(
        role="assistant",
        content=None,
        tool_call_id="call_1",
        tool_calls=[FunctionCall(id="call_1_1", name="Bash", arguments="{}")],
    )

    messages = await toolset.call(tool_call_msg)

    assert len(messages) == 1
    assert "not found" in messages[0].content


class _ProbeTool(Tool):
    """Records how many calls were ever in flight at the same moment."""

    name = "Probe"
    description = "probe"
    parameters = {"type": "object", "properties": {}}

    def __init__(self, block_thread: bool):
        self.block_thread = block_thread
        self.active = 0
        self.peak = 0

    async def call(self, parameters: str, **kwargs) -> str:
        self.active += 1
        self.peak = max(self.peak, self.active)
        if self.block_thread:
            # What Grep and Glob do: block a thread, not the event loop.
            await asyncio.to_thread(time.sleep, 0.05)
        else:
            await asyncio.sleep(0.05)
        self.active -= 1
        return "ok"


def _calls(name: str, n: int) -> Message:
    return Message(
        role="assistant",
        content=None,
        tool_call_id="call_1",
        tool_calls=[FunctionCall(id=f"call_{i}", name=name, arguments="{}") for i in range(n)],
    )


@pytest.mark.parametrize("block_thread", [False, True], ids=["coroutine", "thread"])
async def test_tool_calls_in_one_turn_run_concurrently(block_thread):
    """Assert overlap directly rather than by wall clock.

    ToolSet.call awaited each call before starting the next, so the parallel
    tool calling the paper describes was not happening. The thread variant
    covers what Grep and Glob actually do: block on subprocess.run.
    """
    probe = _ProbeTool(block_thread=block_thread)
    toolset = ToolSet(tools=[probe], work_dir=".")

    messages = await toolset.call(_calls("Probe", 4))

    assert len(messages) == 4
    assert probe.peak == 4, f"peak concurrency was {probe.peak}; calls are still serialised"


async def test_a_malformed_tool_call_does_not_abort_its_siblings():
    """Message.tool_calls permits dicts, whose attribute access raises.

    Under gather an escaping exception would abandon the whole batch with
    siblings still running.
    """
    probe = _ProbeTool(block_thread=False)
    toolset = ToolSet(tools=[probe], work_dir=".")
    msg = _calls("Probe", 2)
    msg.tool_calls.insert(1, {"id": "bad", "name": "Probe"})

    messages = await toolset.call(msg)

    assert len(messages) == 3
    assert "malformed" in messages[1].content
    assert [m.content for m in (messages[0], messages[2])] == ["ok", "ok"]


async def test_results_stay_aligned_with_their_tool_calls():
    """Concurrency must not reorder results relative to the calls they answer."""
    toolset = ToolSet(tools=[_ProbeTool(block_thread=False)], work_dir=".")

    messages = await toolset.call(_calls("Probe", 4))

    assert [m.tool_call_id for m in messages] == ["call_0", "call_1", "call_2", "call_3"]
