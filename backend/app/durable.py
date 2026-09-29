"""Durable JSON state files: every small store the engine keeps in its data folder goes through here (v2.2.3).

The owner lost media.json by accident and the whole media library went with it (fixed in 2.2.2). The audit that
followed found the same shape elsewhere: projects.json (every project in one file) read without a guard, so a damaged
file failed every project; providers.json (the API keys) and presets.json written in place, so a crash mid-write left
a half file, then read as empty, the keys and presets silently gone; the licence records the same. Now:

- write_json writes to a temporary file in the same folder and moves it into place (a reader sees the old file or the
  new, never half of one), after keeping the file it replaces as <name>.bak; a file with credentials keeps its
  owner-only permission, the backup too.
- read_json: a missing file reads as its backup, else the default; a damaged one is set aside as
  <name>.damaged-<time> (for a person to look at, never overwritten), its backup read in its place, and the terminal
  told. A damaged file is never read as empty and then saved over.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path


def _backup(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def _say(text: str) -> None:
    with contextlib.suppress(OSError, ValueError, AttributeError):
        print(f"formcut: {text}", file=sys.__stderr__)


def _parse(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def set_aside(path: Path, reason: Exception | str) -> Path:
    """A damaged file moved out of the way, kept for a person to look at (never overwritten)."""
    aside = path.with_name(f"{path.name}.damaged-{time.strftime('%Y%m%d-%H%M%S')}")
    with contextlib.suppress(OSError):
        os.replace(path, aside)
    _say(f"{path.name} could not be read ({reason}); set aside as {aside.name}")
    return aside


def read_json(path: Path, default):
    """The file's contents; its backup when it is missing or damaged; else default (a fresh copy of it)."""
    try:
        return _parse(path)
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        set_aside(path, exc)
    try:
        data = _parse(_backup(path))
    except (OSError, ValueError):
        return json.loads(json.dumps(default))
    _say(f"{path.name} restored from {path.name}.bak")
    with contextlib.suppress(OSError):
        write_json(path, data, keep_backup=False)
    return data


def write_json(path: Path, data, *, private: bool = False, indent: int | None = 2, keep_backup: bool = True) -> None:
    """The file written whole and moved into place, the version it replaces kept as <name>.bak."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(json.dumps(data, indent=indent), encoding="utf-8")
        if private:
            with contextlib.suppress(OSError):
                os.chmod(temporary, 0o600)
        if keep_backup and path.is_file():
            with contextlib.suppress(OSError):
                shutil.copyfile(path, _backup(path))
                if private:
                    os.chmod(_backup(path), 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
