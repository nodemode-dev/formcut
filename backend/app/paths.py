import os
import sys
from pathlib import Path


def data_root() -> Path:
    configured = os.environ.get("FORMCUT_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    portable = Path(sys.executable).resolve().parent / "portable"
    if getattr(sys, "frozen", False) and portable.is_dir():
        return portable
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "formcut"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "formcut"
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))) / "formcut"


DATA_DIR = data_root()
