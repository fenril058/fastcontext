import json
from pathlib import Path

import aiofiles

from .tool import Tool
from .utils import resolve_within

MAX_LINE = 2000
MAX_LINE_LENGTH = 2000


class ReadTool(Tool):
    name = "Read"
    description: str = Tool.load_desc(Path(__file__).parent / "read.md")
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute path of the file to read.",
            },
            "offset": {
                "type": "integer",
                "description": "The line number to start reading from. Positive values are 1-indexed from the start of the file. Only provide if the file is too large to read at once.",
            },
            "limit": {
                "type": "integer",
                "description": "The number of lines to read. Only provide if the file is too large to read at once.",
            },
        },
        "required": ["path"],
    }

    async def call(self, parameters: str, **kwargs) -> str:
        params: dict = json.loads(parameters)
        file_path = params.get("path")
        offset = params.get("offset", 1)
        limit = params.get("limit")

        if not file_path:
            return "<system-reminder>Error: file path is required</system-reminder>"

        cwd = kwargs.get("cwd", Path.cwd().as_posix())
        target = resolve_within(file_path, cwd)
        if target is None:
            return f"<system-reminder>Permission error: `{file_path}` is not within the working directory `{cwd}`</system-reminder>"

        if not target.exists():
            return f"<system-reminder>Error: {file_path} does not exist</system-reminder>"

        if not isinstance(offset, int) or offset <= 0:
            return "<system-reminder>Error: offset must be a positive integer</system-reminder>"

        if limit is not None and (not isinstance(limit, int) or limit <= 0):
            return "<system-reminder>Error: limit must be a positive integer</system-reminder>"

        async with aiofiles.open(target, mode="r", encoding="utf-8", errors="replace") as f:
            raw_lines = await f.readlines()

        if len(raw_lines) == 0:
            return "File is empty."

        end_line = -1
        if limit is not None:
            end_line = offset + limit - 1
        if end_line == -1 or end_line > len(raw_lines):
            end_line = len(raw_lines)

        lines = []
        total_read_lines = end_line - offset + 1
        if total_read_lines > MAX_LINE:
            end_line = offset + MAX_LINE - 1
        for i in range(offset - 1, end_line):
            if len(raw_lines[i]) > MAX_LINE_LENGTH:
                line = raw_lines[i][:MAX_LINE_LENGTH] + "...\n"
            else:
                line = raw_lines[i]
            prefixed_line = f"{i+1}|{line}"
            lines.append(prefixed_line)
        if total_read_lines > MAX_LINE:
            lines.append("...")
        content = "".join(lines)
        output = f"```{file_path}:{offset}-{end_line}\n{content}\n```"
        return output
