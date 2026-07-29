import json

from fastcontext.agent.llm import FunctionCall, Message
from fastcontext.agent.tool import ToolSet
from fastcontext.agent.tool.read import ReadTool


async def test_toolset_schema_list():
    toolset = ToolSet(tools=[ReadTool()], work_dir=".")
    schema_list = toolset.schema_list()

    assert len(schema_list) == 1
    assert schema_list[0]["function"]["name"] == "Read"


async def test_toolset_call_returns_one_message_per_tool_call(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("line one\nline two\nline three\n", encoding="utf-8")

    toolset = ToolSet(tools=[ReadTool()], work_dir=str(tmp_path))
    tool_call_msg = Message(
        role="assistant",
        content=None,
        tool_call_id="call_1",
        tool_calls=[
            FunctionCall(id="call_1_1", name="Read", arguments=json.dumps({"path": str(target)})),
            FunctionCall(
                id="call_1_2",
                name="Read",
                arguments=json.dumps({"path": str(tmp_path / "missing.md")}),
            ),
        ],
    )

    messages = await toolset.call(tool_call_msg)

    assert [m.tool_call_id for m in messages] == ["call_1_1", "call_1_2"]
    assert all(m.role == "tool" for m in messages)
    assert "line two" in messages[0].content
    assert "does not exist" in messages[1].content


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
