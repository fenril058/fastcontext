import asyncio
import json
import subprocess
from pathlib import Path

from .tool import SUBPROCESS_TIMEOUT, Tool
from .utils import RG_PATH, resolve_within


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
                "description": 'Output mode: "content" shows matching lines (supports -A/-B/-C context, -n line numbers, head_limit), "files_with_matches" shows file paths (supports head_limit), "count" shows match counts (supports head_limit). Defaults to "content".',
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
                "description": 'Limit output to first N lines/entries, equivalent to "| head -N". Works across all output modes: content (limits output lines), files_with_matches (limits file paths), count (limits count entries). Output is capped at 100 lines regardless; only a head_limit between 1 and 99 lowers that, and any other value leaves the cap at 100.',
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
        # Omitting the mode used to fall through to bare ripgrep output, which
        # carries no line numbers when stdout is captured. Citations are the
        # point of this tool, so the documented default has to be real.
        output_mode = params.get("output_mode") or "content"
        before_context = params.get("-B")
        after_context = params.get("-A")
        context = params.get("-C", 3)
        line_number = params.get("-n", True)
        ignore_case = params.get("-i", False)
        type = params.get("type")
        head_limit = params.get("head_limit")
        multiline = params.get("multiline")

        target = resolve_within(path, cwd)
        if target is None:
            return f"<system-reminder>Permission error: `{path}` is not within the working directory `{cwd}`</system-reminder>"

        # to_thread keeps the blocking subprocess off the event loop. Without it
        # the outer asyncio.wait_for in ToolSet.call cannot fire, and sibling
        # tool calls in the same turn cannot make progress.
        output = await asyncio.to_thread(
            run_rg,
            RG_PATH,
            pattern,
            str(target),
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

        if output.startswith("<system-reminder>"):
            # Diagnostics are not results. Truncating a long ripgrep error at
            # 100 lines would strip the closing tag and leave the model with an
            # unterminated envelope followed by "Results truncated".
            return output

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
    except (TypeError, ValueError, OverflowError):
        # OverflowError: JSON permits 1e400, which decodes to float infinity.
        return None


def run_rg(rg_path: str, pattern: str, path: str, **kwargs) -> str:
    # --no-config: ripgrep otherwise reads options from the file named by
    # RIPGREP_CONFIG_PATH, which can supply --pre and reintroduce program
    # execution no matter how carefully this argv is built.
    command = [rg_path, "--no-config"]
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
    elif output_mode == "count":
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

    try:
        output = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return f"<system-reminder>Grep timed out after {SUBPROCESS_TIMEOUT}s. Narrow the pattern, path, or glob.</system-reminder>"

    # ripgrep exits 0 on a match, 1 on no match, and 2 on an actual error. The
    # previous code collapsed 1 and 2 together and returned stderr as if it
    # were search output, so an unparseable regex reached the model looking
    # like a result.
    if output.returncode == 0:
        return output.stdout
    if output.returncode == 1:
        return ""
    return f"<system-reminder>Grep failed: {output.stderr.strip()}</system-reminder>"
