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

## Out of scope

- The model producing wrong, incomplete, or fabricated citations. That is a quality problem.
- Anything that requires the operator to have already set hostile environment variables or configuration.
- Vulnerabilities in `ripgrep`, `uv`, or the model server itself — report those to their own projects.
