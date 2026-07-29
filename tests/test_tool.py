import asyncio
import json
import subprocess

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


def test_glob_keeps_the_pattern_inside_its_own_option(tmp_path, monkeypatch):
    """Assert the argv shape directly.

    Checking only that nothing was executed would pass against the old code
    too, since --glob consumed the following argument either way.
    """
    import fastcontext.agent.tool.glob as glob_module

    seen = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(glob_module.subprocess, "run", fake_run)

    asyncio.run(GlobTool().call(json.dumps({"directory": str(tmp_path), "pattern": "-*.py"}), cwd=str(tmp_path)))

    command = seen["command"]
    assert "--glob=-*.py" in command, command
    assert "-*.py" not in command, "pattern must not appear as a standalone argument"
    assert "--no-config" in command
    assert command.index("--") < command.index(str(tmp_path))


def test_grep_ignores_a_config_file_from_the_environment(tmp_path, monkeypatch):
    """RIPGREP_CONFIG_PATH can supply --pre, which would undo the argv fix."""
    (tmp_path / "payload.sh").write_text(f"touch {tmp_path / 'PWNED'}\n", encoding="utf-8")
    config = tmp_path / "rgcfg"
    config.write_text("--pre=/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv("RIPGREP_CONFIG_PATH", str(config))

    params = {"pattern": "sentinel", "path": str(tmp_path), "output_mode": "content"}
    output = asyncio.run(GrepTool().call(json.dumps(params), cwd=str(tmp_path)))

    assert not (tmp_path / "PWNED").exists(), f"ripgrep honoured the config file: {output}"


def test_grep_context_count_rejects_non_finite_numbers(tmp_path):
    """JSON permits 1e400, which decodes to float infinity and breaks int()."""
    (tmp_path / "a.txt").write_text("sentinel\n", encoding="utf-8")

    params = {
        "pattern": "sentinel",
        "path": str(tmp_path),
        "output_mode": "content",
        "-C": json.loads("1e400"),
    }
    output = asyncio.run(GrepTool().call(json.dumps(params), cwd=str(tmp_path)))

    assert "sentinel" in output


def test_grep_count_mode_is_wired_up(tmp_path):
    """The schema offers "count"; the implementation checked for "count_matches"."""
    (tmp_path / "a.txt").write_text("sentinel\nsentinel\nother\n", encoding="utf-8")

    params = {"pattern": "sentinel", "path": str(tmp_path), "output_mode": "count"}
    output = asyncio.run(GrepTool().call(json.dumps(params), cwd=str(tmp_path)))

    # --count-matches reports the match total per file, not the matching lines.
    assert output.strip().endswith(":2"), output


def test_grep_default_output_mode_is_content(tmp_path):
    """Omitting output_mode must behave exactly like asking for content.

    It used to fall through to bare ripgrep output, which carries no line
    numbers when stdout is captured rather than attached to a terminal — so
    the default call shape produced output no citation could be built from.
    """
    (tmp_path / "a.txt").write_text("aaa\nbbb sentinel\nccc\n", encoding="utf-8")

    omitted = asyncio.run(
        GrepTool().call(json.dumps({"pattern": "sentinel", "path": str(tmp_path)}), cwd=str(tmp_path))
    )
    explicit = asyncio.run(
        GrepTool().call(
            json.dumps({"pattern": "sentinel", "path": str(tmp_path), "output_mode": "content"}),
            cwd=str(tmp_path),
        )
    )

    assert omitted == explicit
    assert "2:bbb sentinel" in omitted, omitted

    schema = GrepTool().schema()["function"]["parameters"]["properties"]
    assert 'Defaults to "content"' in schema["output_mode"]["description"]


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


def _escape_layout(tmp_path):
    """work_dir is box/; the interpreter sits in box/sub; the secret is outside box."""
    box = tmp_path / "box"
    (box / "sub").mkdir(parents=True)
    (box / "ok.txt").write_text("innocuous\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("TOP-SECRET-SENTINEL\n", encoding="utf-8")
    return box, outside


def test_grep_relative_path_cannot_escape_the_work_dir(tmp_path, monkeypatch):
    """The check and ripgrep must resolve a relative path against the same base.

    The check used the interpreter's cwd while ripgrep used the tool's cwd, so
    "../outside" was approved as box/outside and then searched as
    tmp_path/outside.
    """
    box, _ = _escape_layout(tmp_path)
    monkeypatch.chdir(box / "sub")

    params = {"pattern": "TOP-SECRET-SENTINEL", "path": "../outside", "output_mode": "content"}
    output = asyncio.run(GrepTool().call(json.dumps(params), cwd=str(box)))

    assert "TOP-SECRET-SENTINEL" not in output, output
    assert "Permission error" in output


def test_read_relative_path_cannot_escape_the_work_dir(tmp_path, monkeypatch):
    box, _ = _escape_layout(tmp_path)
    monkeypatch.chdir(box / "sub")

    output = asyncio.run(ReadTool().call(json.dumps({"path": "../outside/secret.txt"}), cwd=str(box)))

    assert "TOP-SECRET-SENTINEL" not in output, output
    assert "Permission error" in output


def test_glob_relative_path_cannot_escape_the_work_dir(tmp_path, monkeypatch):
    box, _ = _escape_layout(tmp_path)
    monkeypatch.chdir(box / "sub")

    output = asyncio.run(GlobTool().call(json.dumps({"directory": "../outside", "pattern": "*"}), cwd=str(box)))

    assert "secret.txt" not in output, output
    assert "Permission error" in output


def test_relative_paths_still_resolve_against_the_work_dir(tmp_path, monkeypatch):
    """Hardening must not break the ordinary case of a path relative to work_dir."""
    box, _ = _escape_layout(tmp_path)
    monkeypatch.chdir(tmp_path)

    output = asyncio.run(ReadTool().call(json.dumps({"path": "ok.txt"}), cwd=str(box)))

    assert "innocuous" in output, output


def test_unusable_paths_are_rejected_not_raised(tmp_path):
    """An embedded NUL raises out of the stat call; it must not reach the model."""
    output = asyncio.run(ReadTool().call(json.dumps({"path": "nul\x00path"}), cwd=str(tmp_path)))

    assert "Permission error" in output
    assert "ValueError" not in output


def test_absolute_paths_outside_the_work_dir_are_rejected(tmp_path):
    """Covers the drive-relative and UNC forms Windows can produce, too."""
    box = tmp_path / "box"
    box.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("TOP-SECRET-SENTINEL\n", encoding="utf-8")

    output = asyncio.run(ReadTool().call(json.dumps({"path": str(outside)}), cwd=str(box)))

    assert "TOP-SECRET-SENTINEL" not in output
    assert "Permission error" in output


def test_grep_reports_absolute_paths(tmp_path, monkeypatch):
    """Deliberate consequence of handing ripgrep the resolved target.

    The system prompt asks the model for absolute citations, so absolute
    ripgrep output is what it should be reasoning from — especially when the
    process is not sitting at work_dir.
    """
    (tmp_path / "a.txt").write_text("sentinel\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    output = asyncio.run(
        GrepTool().call(json.dumps({"pattern": "sentinel", "path": "."}), cwd=str(tmp_path))
    )

    assert str(tmp_path / "a.txt") in output, output
