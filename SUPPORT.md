# Support

This is an independently maintained fork of a repository that is no longer available upstream. It is
maintained by one person as time allows. There is no company behind it and no support commitment.

## Questions and bugs

Use [GitHub Issues](https://github.com/fenril058/fastcontext/issues). Search first — the upstream
issue tracker is gone, so anything previously discussed there has to be re-established here.

A useful report includes:

- The FastContext commit.
- The model and endpoint (`FC_MODEL`, and whether `FC_BASE_URL` points at Ollama, vLLM, or something else).
- The exact command, and the trajectory file if you can share it — `--traj` writes one, and `--verbose`
  prints the turns.

For suspected vulnerabilities follow [SECURITY.md](SECURITY.md) instead of opening an issue.

## Questions this project cannot answer

- **The paper.** Methodology, results, and training details belong to
  [arXiv:2606.14066](https://arxiv.org/abs/2606.14066) and its authors, who have no involvement here.
- **The model weights.** The original `microsoft/FastContext-1.0-*` repositories no longer resolve.
  See the README for the community re-uploads; their provenance cannot be verified from here.
