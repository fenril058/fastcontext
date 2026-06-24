import os

from fastcontext.agent.agent import Agent
from fastcontext.agent.llm import LLM
from fastcontext.agent.tool.tool import ToolSet
from fastcontext.agent.tool.utils import RG_PATH
from fastcontext.agent.utils import load_system_prompt


def make_fastcontext_agent(
    trajectory_file: str,
    work_dir: str,
    **kwargs,
) -> Agent:
    name = "FastContext"
    system_prompt = kwargs.get("system_prompt", None)
    if system_prompt is None:
        system_prompt = load_system_prompt(work_dir)

    llm = LLM(
        model=os.getenv("MODEL"),
        api_key=os.getenv("API_KEY"),
        base_url=os.getenv("BASE_URL"),
    )

    from fastcontext.agent.tool.glob import GlobTool
    from fastcontext.agent.tool.grep import GrepTool
    from fastcontext.agent.tool.read import ReadTool

    if not RG_PATH:
        raise RuntimeError(
            "Grep tool requires ripgrep (rg) to be installed, but it was not found in current environment.\n"
            "Install it from: https://github.com/BurntSushi/ripgrep"
        )

    toolset = ToolSet([ReadTool(), GlobTool(), GrepTool()], work_dir=work_dir)
    return Agent(
        name=name,
        system_prompt=system_prompt,
        llm=llm,
        toolset=toolset,
        trajectory_file=trajectory_file,
        work_dir=work_dir,
    )
