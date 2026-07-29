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

These are real, understood, and deliberately not fixed. Reporting them is not wasted effort — say so if
you think the reasoning is wrong — but they will not be treated as new findings.

**Symlink replacement between the check and the read.** `resolve_within` in
`src/fastcontext/agent/tool/utils.py` resolves a path, follows any symlinks, and confirms the result sits
inside the working directory. The file is opened, or handed to `ripgrep`, some moments later. An adversary
who can write to the tree *while a search is running* could swap a directory component for a symlink
pointing outside in that window.

Not fixed because closing it properly means abandoning paths-as-strings for file descriptors and
`openat`-style traversal, and `Grep` passes a path to `ripgrep`, at which point this code has no control
left. A partial fix would mostly buy the false impression that the gap is closed. The prerequisite — an
attacker with concurrent write access to the repository you are exploring — is also a different situation
from the one this tool is built for.

**Blocking metadata calls on the event loop.** `resolve_within` and `Path.is_dir` run synchronously in the
tool coroutines rather than on a worker thread. On a slow or network filesystem they can stall the whole
agent loop, including sibling tool calls in the same turn.

Not fixed because these are bounded `stat` operations, microseconds on a local disk — orders of magnitude
below the `subprocess.run` calls that were moved to threads for exactly this reason. Moving them too would
add machinery in four places for no measurable benefit on the filesystems this tool is actually pointed at.

## Out of scope

- The model producing wrong, incomplete, or fabricated citations. That is a quality problem.
- Anything that requires the operator to have already set hostile environment variables or configuration.
- Vulnerabilities in `ripgrep`, `uv`, or the model server itself — report those to their own projects.
