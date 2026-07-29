import asyncio
import json
import subprocess
from pathlib import Path

from .tool import SUBPROCESS_TIMEOUT, Tool
from .utils import RG_PATH, resolve_within


def run(directory: str, pattern: str, cwd: str) -> str:
    # `--glob=value` and the `--` terminator keep a pattern or directory that
    # begins with a dash from being parsed as a ripgrep flag. See run_rg in
    # grep.py for why that matters.
    command = [RG_PATH, "--no-config", "--files", f"--glob={pattern}", "--", directory]
    timeout = SUBPROCESS_TIMEOUT
    try:
        output = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return f"<system-reminder>Glob timed out after {timeout}s</system-reminder>"

    # Same exit-code contract as Grep: 0 matched, 1 matched nothing, 2 failed.
    if output.returncode == 0:
        return output.stdout
    if output.returncode == 1:
        return ""
    return f"<system-reminder>Glob failed: {output.stderr.strip()}</system-reminder>"


class GlobTool(Tool):
    name = "Glob"
    description: str = Tool.load_desc(Path(__file__).parent / "glob.md")
    parameters = {
        "type": "object",
        "properties": {
            "directory": {
                "type": "string",
                "description": "The absolute path of the directory to search in. If not provided, the current working directory will be used.",
            },
            "pattern": {
                "type": "string",
                "description": "The glob pattern to match files or directories.",
            },
        },
        "required": ["pattern"],
    }

    async def call(self, parameters: str, **kwargs) -> str:
        cwd = kwargs.get("cwd", str(Path.cwd()))
        params: dict = json.loads(parameters)
        directory = params.get("directory", cwd)
        pattern = params.get("pattern")

        target = resolve_within(directory, cwd)
        if target is None:
            return f"<system-reminder>Permission error: `{directory}` is not within the working directory `{cwd}`</system-reminder>"
        if not target.is_dir():
            return f"<system-reminder>Error: directory `{directory}` does not exist or is not a directory.</system-reminder>"

        output = await asyncio.to_thread(run, str(target), pattern, cwd=cwd)

        limit = 100
        matched_files = output.splitlines()
        if len(matched_files) > limit:
            matched_files = matched_files[:limit]
            matched_files.append(
                f"Results are truncated: showing first {limit} results. Consider using a more specific path or pattern."
            )

        if not matched_files:
            return "No files found"
        return "\n".join(matched_files)
