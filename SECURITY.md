# Security

This is an independently maintained fork. **Do not report vulnerabilities here to the Microsoft
Security Response Centre** — MSRC does not cover this repository, and a report sent there will not
reach anyone who can fix it.

## Reporting

Report privately through [GitHub's security advisory form](https://github.com/fenril058/fastcontext/security/advisories/new)
rather than as a public issue.

Please include the FastContext commit, the model and endpoint in use, and the smallest reproduction
you can manage. There is no bounty and no response-time guarantee: this is maintained by one person
in their own time.

## Scope

FastContext runs a language model's tool calls against a repository you point it at, and that
repository is untrusted input — its content reaches the model, and the model chooses the tool
arguments. Findings in that path matter most here:

- A tool argument escaping into the underlying `ripgrep` invocation.
- Reads or searches escaping the working directory passed to the agent.
- Anything that lets an explored repository cause writes outside the configured trajectory file,
  network access, or command execution. The trajectory is a deliberate write: every message and
  every repository excerpt is appended to it, at `.fastcontext/` unless `--traj` says otherwise.

The tools are meant to be read-only. Any way to make them otherwise is a vulnerability, including
through prompt injection from a file in the repository being explored.

## Known and accepted

These are real, understood, and deliberately not fixed. They will not be treated as new findings, but the
reasoning below is a judgement, not a proof — say so if you think it is wrong. A variant with weaker
prerequisites than the ones described here is in scope and worth reporting.

**Symlink replacement between the check and the read.** `resolve_within` in
`src/fastcontext/agent/tool/utils.py` resolves a path, follows any symlinks, and confirms the result sits
inside the working directory. The file is opened, or handed to `ripgrep`, some moments later. An adversary
who can write to the tree *while a search is running* could swap a directory component for a symlink
pointing outside in that window.

Not fixed because every option is substantially more involved than it looks. Re-checking after the fact
narrows the window without closing it, and cannot undo a disclosure that already happened. Doing it
properly means abandoning paths-as-strings for file descriptors and `openat`-style traversal. `Grep` is
harder still, since it hands a path to a separate process — not impossible (one could keep an anchored
directory descriptor open across the fork and address the target through it, sandbox `ripgrep`, or search
a snapshot) but non-portable and well beyond a targeted fix. The prerequisite — an attacker with
concurrent write access to the repository you are exploring — is also a different situation from the one
this tool is built for.

If you have a portable approach that closes it, that is worth an issue.

**Blocking path resolution on the event loop.** `resolve_within` — and `Path.is_dir` in Glob, `Path.exists`
in Read — run synchronously in the tool coroutines rather than on a worker thread. On a slow or network
filesystem they can stall the whole agent loop, including sibling tool calls in the same turn. That much is
straightforwardly true.

Not fixed because the work is normally small: path resolution and one or two metadata lookups, against the
`subprocess.run` calls that were moved to threads because they can run for seconds. `Path.resolve` is not
strictly constant-time — it scales with path depth and symlink chains — so this is a judgement that the
common case dominates, not a proof. It has not been measured on a network filesystem. If you have a
workload where it matters, that measurement would be the thing to bring.

## Out of scope

- The model producing wrong, incomplete, or fabricated citations. That is a quality problem.
- Anything that requires the operator to have already set hostile environment variables or configuration.
- Vulnerabilities in `ripgrep`, `uv`, or the model server itself — report those to their own projects.
