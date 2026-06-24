import os
import platform
import shutil


def _find_existing_rg() -> str | None:
    rg_name = "rg.exe" if platform.system() == "Windows" else "rg"
    rg = shutil.which(rg_name)
    if rg and os.path.exists(rg):
        return rg
    return None


RG_PATH = _find_existing_rg()
