import asyncio
import json
from asyncio import Future
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from fastcontext.agent.llm import Message

MAX_TOOLRUN_TIMEOUT = 10

# Subprocess-backed tools bound themselves below the outer guard, so a slow
# ripgrep is reported as such and the process is actually killed, rather than
# being abandoned by an outer timeout that cannot reach it. Clamped so that
# lowering MAX_TOOLRUN_TIMEOUT cannot make this zero or negative.
SUBPROCESS_TIMEOUT = max(1, MAX_TOOLRUN_TIMEOUT - 2)


class ToolResult(BaseModel):
    tool_call_id: str
    output: str
    failed: bool


ToolResultFuture = Future[ToolResult]

type ToolOutput = ToolResult | ToolResultFuture


class Tool:
    name: str
    description: str
    parameters: dict[str, Any]

    async def call(self, parameters: str, **kwargs) -> str:
        raise NotImplementedError("Tool.call must be implemented by subclasses.")

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @staticmethod
    def load_desc(path: str) -> str:
        desc = Path(path).read_text(encoding="utf-8")
        return desc


class ToolSet:
    _tool_dict: dict[str, Tool] = {}

    def __init__(self, tools: list[Tool], work_dir: str):
        self._tool_dict = {tool.name: tool for tool in tools}
        self.work_dir = work_dir

    def schema_list(self) -> list[dict[str, Any]]:
        return [tool.schema() for tool in self._tool_dict.values()]

    async def _single_tool_call(self, tool_name: str, parameters: str, toll_call_id: str) -> ToolOutput:
        if tool_name not in self._tool_dict:
            return ToolResult(
                tool_call_id=toll_call_id,
                failed=True,
                output=f"Tool `{tool_name}` not found.",
            )

        tool = self._tool_dict[tool_name]
        try:
            json.loads(parameters or "{}")
        except json.JSONDecodeError:
            return ToolResult(
                tool_call_id=toll_call_id,
                failed=True,
                output=f"Tool `{tool_name}` arguments are invalid.",
            )

        async def _call():
            try:
                output = await tool.call(parameters, cwd=self.work_dir)
                return ToolResult(tool_call_id=toll_call_id, failed=False, output=output)
            except Exception as e:
                return ToolResult(tool_call_id=toll_call_id, failed=True, output=str(e))

        # return asyncio.create_task(_call())
        return await _call()

    async def call(self, msg: Message) -> list[Message]:
        if not msg.tool_calls:
            return []

        async def _guarded(index: int, c) -> ToolResult:
            # Message.tool_calls is typed list[dict | FunctionCall], so the
            # attribute reads below can raise before _single_tool_call's own
            # handler is reached. Under gather that would abort the batch and
            # leave siblings running, so nothing may escape this coroutine.
            call_id = getattr(c, "id", None) or f"call_{index}"
            try:
                name = c.name
                return await asyncio.wait_for(
                    self._single_tool_call(name, c.arguments, c.id), timeout=MAX_TOOLRUN_TIMEOUT
                )
            except TimeoutError:
                return ToolResult(
                    tool_call_id=call_id,
                    failed=True,
                    output=f"Tool `{getattr(c, 'name', '?')}` timed out after {MAX_TOOLRUN_TIMEOUT}s.",
                )
            except Exception as e:
                return ToolResult(tool_call_id=call_id, failed=True, output=f"Tool call is malformed: {e}")

        # gather preserves argument order, so results still line up with the
        # tool_calls they answer.
        tool_results: list[ToolResult] = list(
            await asyncio.gather(*(_guarded(i, c) for i, c in enumerate(msg.tool_calls)))
        )

        tools_result_messages = []
        for tr in tool_results:
            tools_result_messages.append(
                Message(
                    role="tool",
                    content=tr.output,
                    tool_call_id=tr.tool_call_id,
                )
            )
        return tools_result_messages
