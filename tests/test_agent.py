import os

import pytest

from conftest import requires_llm
from fastcontext.agent.agent import Agent
from fastcontext.agent.llm import LLM
from fastcontext.agent.tool import ToolSet
from fastcontext.agent.tool.read import ReadTool

pytestmark = [pytest.mark.requires_llm, requires_llm]


async def test_agent(tmp_path):
    (tmp_path / "README.md").write_text(
        "FastContext is a repository exploration subagent.\n",
        encoding="utf-8",
    )

    llm = LLM(
        model=os.getenv("FC_MODEL") or os.getenv("MODEL"),
        api_key=os.getenv("FC_API_KEY") or os.getenv("API_KEY"),
        base_url=os.getenv("FC_BASE_URL") or os.getenv("BASE_URL"),
    )

    work_dir = str(tmp_path)
    toolset = ToolSet(tools=[ReadTool()], work_dir=work_dir)

    agent = Agent(
        name="TestAgent",
        system_prompt="You are a helpful coding assistant.",
        llm=llm,
        toolset=toolset,
        trajectory_file=str(tmp_path / "trajectory.jsonl"),
        work_dir=work_dir,
    )

    result = await agent.run(
        f"Please summarize file content of '{tmp_path / 'README.md'}' to one sentence.",
        max_turns=5,
    )

    assert result
