import json
import subprocess
from pathlib import Path

from .tool import Tool
from .utils import RG_PATH


class GrepTool(Tool):
    name = "Grep"
    description: str = Tool.load_desc(Path(__file__).parent / "grep.md")
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "The regular expression pattern to search for in file contents",
            },
            "path": {
                "type": "string",
                "description": "File or directory to search in (rg pattern -- PATH). Defaults to current working directory.",
            },
            "glob": {
                "type": "string",
                "description": 'Glob pattern to filter files (e.g. "*.js", "*.{ts,tsx}") - maps to rg --glob',
            },
            "output_mode": {
                "type": "string",
                "enum": ["content", "files_with_matches", "count"],
                "description": 'Output mode: "content" shows matching lines (supports -A/-B/-C context, -n line numbers, head_limit), "files_with_matches" shows file paths (supports head_limit), "count" shows match counts (supports head_limit). Defaults to "files_with_matches".',
            },
            "-B": {
                "type": "number",
                "description": 'Number of lines to show before each match (rg -B). Requires output_mode: "content", ignored otherwise.',
            },
            "-A": {
                "type": "number",
                "description": 'Number of lines to show after each match (rg -A). Requires output_mode: "content", ignored otherwise.',
            },
            "-C": {
                "type": "number",
                "description": 'Number of lines to show before and after each match (rg -C). Requires output_mode: "content", ignored otherwise.',
            },
            "-n": {
                "type": "boolean",
                "description": 'Show line numbers in output (rg -n). Requires output_mode: "content", ignored otherwise. Defaults to true.',
            },
            "-i": {
                "type": "boolean",
                "description": "Case insensitive search (rg -i)",
            },
            "type": {
                "type": "string",
                "description": "File type to search (rg --type). Common types: js, py, rust, go, java, etc. More efficient than include for standard file types.",
            },
            "head_limit": {
                "type": "number",
                "minimum": 0,
                "description": 'Limit output to first N lines/entries, equivalent to "| head -N". Works across all output modes: content (limits output lines), files_with_matches (limits file paths), count (limits count entries). When unspecified, shows all results from ripgrep.',
            },
            "multiline": {
                "type": "boolean",
                "description": "Enable multiline mode where . matches newlines and patterns can span lines (rg -U --multiline-dotall). Default: false.",
            },
        },
        "required": ["pattern"],
    }

    async def call(self, parameters: str, **kwargs) -> str:
        params: dict = json.loads(parameters)
        cwd = kwargs.get("cwd", str(Path.cwd()))
        # ripgrep parameters
        pattern = params.get("pattern")
        path = params.get("path", cwd)
        glob = params.get("glob")
        output_mode = params.get("output_mode")
        before_context = params.get("-B")
        after_context = params.get("-A")
        context = params.get("-C", 3)
        line_number = params.get("-n", True)
        ignore_case = params.get("-i", False)
        type = params.get("type")
        head_limit = params.get("head_limit")
        multiline = params.get("multiline")

        if not Path(path).resolve().is_relative_to(Path(cwd).resolve()):
            return f"<system-reminder>Permission error: `{path}` is not within the working directory `{cwd}`</system-reminder>"

        output = run_rg(
            RG_PATH,
            pattern,
            path,
            cwd=cwd,
            glob=glob,
            output_mode=output_mode,
            before_context=before_context,
            after_context=after_context,
            context=context,
            line_number=line_number,
            ignore_case=ignore_case,
            type=type,
            multiline=multiline,
        )
        if not output:
            return "No matches found"

        limit = 100
        if head_limit is not None:
            if head_limit < limit and head_limit > 0:
                limit = head_limit

        lines = output.splitlines()
        if len(lines) > limit:
            output = "\n".join(lines[:limit])
            truncated_hit = f"Results truncated to first {limit} lines"
            output += f"\n{truncated_hit}"
        return output


def _context_flag(value) -> str | None:
    """Coerce a model-supplied context count to a non-negative integer."""
    try:
        return str(max(0, int(value)))
    except (TypeError, ValueError):
        return None


def run_rg(rg_path: str, pattern: str, path: str, **kwargs) -> str:
    command = [rg_path]
    if kwargs.get("glob"):
        # The `--flag=value` form is used throughout so that a value beginning
        # with a dash cannot be reinterpreted as the next flag.
        command.append(f"--glob={kwargs['glob']}")
    if kwargs.get("ignore_case"):
        command.append("--ignore-case")
    if kwargs.get("type"):
        command.append(f"--type={kwargs['type']}")
    if kwargs.get("multiline"):
        command.append("--multiline")
        command.append("--multiline-dotall")
    output_mode = kwargs.get("output_mode")
    if output_mode == "content":
        for flag, key in (("-B", "before_context"), ("-A", "after_context"), ("-C", "context")):
            if kwargs.get(key) is not None:
                count = _context_flag(kwargs[key])
                if count is not None:
                    command.append(f"{flag}{count}")
        if kwargs.get("line_number"):
            command.append("-n")
    elif output_mode == "files_with_matches":
        command.append("--files-with-matches")
    elif output_mode == "count_matches":
        command.append("--count-matches")

    # --heading and --color never
    command.append("--heading")
    command.append("--color")
    command.append("never")

    # Pass the pattern with -e and terminate option parsing with --, so neither
    # the pattern nor the path can be read as a ripgrep flag. Without this, a
    # pattern of "--pre=/bin/sh" makes ripgrep execute that program once per
    # file, turning a read-only search tool into arbitrary code execution.
    command.extend(["-e", pattern, "--"])
    if path:
        command.append(path)

    cwd = kwargs.get("cwd", str(Path.cwd()))

    output = subprocess.run(command, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    if output.returncode == 0:
        output_text = (
            output.stdout if isinstance(output.stdout, str) else output.stdout.decode("utf-8", errors="replace")
        )
    else:
        output_text = (
            output.stderr if isinstance(output.stderr, str) else output.stderr.decode("utf-8", errors="replace")
        )
    return output_text
