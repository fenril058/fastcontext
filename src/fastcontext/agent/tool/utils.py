import os
import platform
import shutil
from pathlib import Path


def resolve_within(path: str, cwd: str) -> Path | None:
    """Resolve a model-supplied path against the tool's working directory.

    Returns None when the result escapes `cwd`.

    Relative paths must be resolved against `cwd` rather than the interpreter's
    current directory. Otherwise the permission check and the operation that
    follows it can disagree about which file is meant: ripgrep receives `cwd`
    via subprocess, so `../outside` was checked as CWD/../outside and then
    searched as cwd/../outside, and the two land in different places whenever
    the process is not sitting exactly at `cwd`.
    """
    root = Path(cwd).resolve()
    # An absolute `path` replaces `root` here, which is what we want; the
    # containment check below is what rejects absolute paths outside the tree.
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        return None
    return target


def _find_existing_rg() -> str | None:
    rg_name = "rg.exe" if platform.system() == "Windows" else "rg"
    rg = shutil.which(rg_name)
    if rg and os.path.exists(rg):
        return rg
    return None


RG_PATH = _find_existing_rg()
