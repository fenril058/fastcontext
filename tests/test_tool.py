import asyncio
import json

from fastcontext.agent.tool.glob import GlobTool
from fastcontext.agent.tool.grep import GrepTool
from fastcontext.agent.tool.read import ReadTool


def test_grep_tool():
    grep = GrepTool()
    params = {
        "pattern": "grep.call",
        "path": ".",
        "glob": "*.py",
        "output_mode": "content",
        "head_limit": 100,
        "-C": 3,
    }

    output = asyncio.run(grep.call(json.dumps(params)))
    print(output)

    # /testbed/**: No such file or directory (os error 2)
    params = {"pattern": "arithmetic", "path": "/testbed/**", "output_mode": "files_with_matches", "head_limit": 200}
    output = asyncio.run(grep.call(json.dumps(params)))
    print(output)


def test_glob_tool():
    glob = GlobTool()
    params = {
        "directory": "./src",
        "pattern": "**/*.py",
    }
    output = asyncio.run(glob.call(json.dumps(params)))
    print(output)


def test_grep_pattern_cannot_become_a_ripgrep_flag(tmp_path):
    """A pattern beginning with a dash must be searched for, not parsed as a flag.

    ripgrep's --pre runs an arbitrary program once per file. Before the pattern
    was passed via -e, a pattern of "--pre=/bin/sh" turned this read-only search
    tool into arbitrary code execution against the repository being explored.
    """
    (tmp_path / "payload.sh").write_text(f"touch {tmp_path / 'PWNED'}\n", encoding="utf-8")

    grep = GrepTool()
    params = {"pattern": "--pre=/bin/sh", "path": str(tmp_path), "output_mode": "content"}
    output = asyncio.run(grep.call(json.dumps(params), cwd=str(tmp_path)))

    assert not (tmp_path / "PWNED").exists(), f"ripgrep executed the payload: {output}"
    assert "preprocessor" not in output


def test_grep_pattern_with_leading_dash_still_matches(tmp_path):
    """Hardening must not break legitimate searches for dash-prefixed text."""
    (tmp_path / "arrow.txt").write_text("value --> target\n", encoding="utf-8")

    grep = GrepTool()
    params = {"pattern": "-->", "path": str(tmp_path), "output_mode": "content"}
    output = asyncio.run(grep.call(json.dumps(params), cwd=str(tmp_path)))

    assert "value --> target" in output


def test_glob_pattern_cannot_become_a_ripgrep_flag(tmp_path):
    (tmp_path / "payload.sh").write_text(f"touch {tmp_path / 'PWNED'}\n", encoding="utf-8")

    glob = GlobTool()
    params = {"directory": str(tmp_path), "pattern": "--pre=/bin/sh"}
    output = asyncio.run(glob.call(json.dumps(params), cwd=str(tmp_path)))

    assert not (tmp_path / "PWNED").exists(), f"ripgrep executed the payload: {output}"


def test_read_tool_path_traversal():
    read = ReadTool()
    cwd = "/tmp/"

    # Should be blocked: outside cwd
    output = asyncio.run(read.call(json.dumps({"path": "/etc/passwd"})))
    assert "<system-reminder>Permission error" in output, f"Expected permission error, got: {output}"

    # Should be blocked: not within cwd
    output = asyncio.run(read.call(json.dumps({"path": f"{cwd}/README.md"}), cwd=cwd))
    assert "<system-reminder>Error:" in output

    from pathlib import Path

    cwd = Path.cwd().as_posix()
    output = asyncio.run(read.call(json.dumps({"path": f"{cwd}/test_llm.py"}), cwd="./"))


if __name__ == "__main__":
    test_grep_tool()
    test_glob_tool()
    test_read_tool_path_traversal()
