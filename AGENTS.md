# Working on FastContext

Non-obvious constraints, learned by breaking them.
Everything here cost a bug; none of it is derivable by reading the code.

## Provenance

This is an independently maintained fork of `microsoft/fastcontext`, which no longer exists.
Do not look for an upstream to sync with or file issues against; there is none.

Three branches survive only in this repository's history, recovered before the upstream vanished: `salvage/dependabot-*`.
`training/`, `serving/`, and two removed benchmark scripts are likewise reachable only through git history — see the README for the incantations.
Never re-clone this repository from scratch expecting parity.

The code and weights are MIT.
Redistribution is permitted subject to retaining the notice; the original repository disappearing does not revoke that.

## The tool descriptions are the interface

`src/fastcontext/agent/tool/*.md` and the `description` strings in each tool's `parameters` schema are not documentation for humans.
They are the text a 4B model plans against.

A false claim there is a bug with the same severity as a false claim in code.
Fixed instances included: results "sorted by modification time" that were never sorted, an "Agent tool" that does not exist, a 500-character truncation width that was really 2000, and a default `output_mode` that disagreed between the schema, `grep.md`, and the implementation.

**Change the description in the same commit that changes the behaviour.**
Prefer a test that ties the string to the constant (see `test_read_description_states_the_real_line_truncation_width`) over a test that asserts the string alone.

## Tool arguments are attacker-influenced

`pattern`, `path`, `glob`, `type`, `head_limit` and friends are chosen by the model, not by the user.
The model reads the repository under exploration, which is untrusted input.
Treat every tool parameter as reachable by prompt injection.

Two of these values cross into `subprocess` argv.
Keep them there: pass the pattern with `-e`, terminate options with `--`, use the `--flag=value` joined form, and keep `--no-config` so `RIPGREP_CONFIG_PATH` cannot inject `--pre`.
A pattern beginning with a dash was arbitrary code execution before those four measures existed.

## Never derive a value from an off-spec input

`int(True)` is `1`.
`int(1.9)` is `1`.
Both once made `head_limit` truncate two hundred matching lines to one, reported as a deliberate limit.

The trap is the shape `try: n = int(value) except: fallback` — it *looks* defensive while still deriving the result from a value the schema forbids.
Accept the exact types you mean, and fall back to a safe constant for everything else.
`_head_limit` in `grep.py` is the pattern to copy; `_context_flag` beside it is deliberately laxer and is not.

Silently returning almost no results is worse than raising.
A search tool that quietly returns one line looks successful, and the caller concludes the symbol does not exist.

## Errors reach the model only as text

`ToolSet.call` discards `ToolResult.failed` when it builds `Message` objects.
Setting that flag changes nothing observable.
Wrap real failures in `<system-reminder>`, the convention the tools already use, and return them before the truncation step so a long diagnostic keeps its closing tag.

ripgrep exits **0** on a match, **1** on no match, **2** on an error.
Collapsing 1 and 2 makes a malformed regex indistinguishable from an absent symbol.

## `work_dir` is not the process working directory

The CLI sets them equal, so CLI testing will not reveal a difference.
Library callers and the benchmark harness do not — the README's own programmatic example passes `work_dir="/path/to/repo"` from wherever the caller happens to run.

Resolve every model-supplied path with `resolve_within(path, cwd)` and operate on the value it returns.
Resolving against the process directory once let a relative path read outside `work_dir`, because the containment check and ripgrep disagreed about which file was meant.

## Blocking calls defeat the timeout that appears to guard them

`asyncio.wait_for(..., timeout=MAX_TOOLRUN_TIMEOUT)` in `ToolSet.call` cannot fire if the coroutine never yields.
`subprocess.run` on the event loop thread also stalls every sibling call in the same turn.

Route blocking work through `asyncio.to_thread` **and** give the subprocess its own `timeout=`.
The outer guard abandons a call; only the inner one kills the process.

