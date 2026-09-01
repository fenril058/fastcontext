# Working on FastContext

## Repository provenance

Do not sync with or report issues to `microsoft/fastcontext`; the upstream repository no longer exists.

Do not replace this checkout with a clone of the vanished upstream; recovered branches and removed files exist only in this fork's history.

## Model-facing tool contract

Treat `src/fastcontext/agent/tool/*.md` and tool-parameter `description` strings as model-facing interfaces.

When tool behavior changes, update the corresponding descriptions in the same change.

Test descriptions against the behavior's source of truth, such as a shared constant, instead of duplicating literals in tests.

## Untrusted tool arguments

Treat every tool argument as attacker-controlled because the model derives arguments from untrusted repository content.

Pass model-supplied subprocess values only as argv elements.

For ripgrep, pass patterns with `-e`, end option parsing with `--`, join option values as `--flag=value`, and retain `--no-config`.

Explicitly whitelist accepted representations of model-supplied numeric values and use a safe default for all others; do not apply blanket `int(...)` coercion.

Follow `_head_limit` in `grep.py` for this validation pattern; `_context_flag` is intentionally more permissive.

## Tool failures

Represent real tool failures in output text with `<system-reminder>` because `ToolResult.failed` is not forwarded to the model.

Return failure output before result truncation so the closing `</system-reminder>` is preserved.

Handle ripgrep exit code 1 as no match and exit code 2 as an error.

## Paths and timeouts

Resolve every model-supplied path with `resolve_within(path, cwd)` and operate only on the returned path; never resolve it against the process working directory.

Run blocking subprocess work through `asyncio.to_thread` and give the subprocess its own timeout; `asyncio.wait_for` alone cannot stop a blocked event loop or kill the process.
