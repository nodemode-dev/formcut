"""No console windows for the programs the engine runs on Windows.

The desktop app starts the engine without a console. On Windows, a process with
no console that starts a console program (ffmpeg, ffprobe, the speech runtime's
Python) makes Windows open a new console window for it, so imports, thumbnails
and exports would each flash a black window. Every process the engine starts
goes through subprocess.Popen (subprocess.run and the rest build on it), so one
wrapper, installed before any engine module runs, adds CREATE_NO_WINDOW to all
of them, including any added later. A call that asks for a console of its own,
or for a detached process, keeps what it asked for.
"""

from __future__ import annotations

import functools
import subprocess

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_CONSOLE = 0x00000010
DETACHED_PROCESS = 0x00000008
_MARK = "__formcut_no_window__"


def creation_flags(requested: int) -> int:
    """The flags a new process is started with: the caller's, plus no window unless it asked for a console."""
    if requested & (CREATE_NEW_CONSOLE | DETACHED_PROCESS):
        return requested
    return requested | CREATE_NO_WINDOW


def quiet_subprocesses() -> None:
    """Install the wrapper on subprocess.Popen; installing it twice changes nothing."""
    original = subprocess.Popen.__init__
    if getattr(original, _MARK, False):
        return

    @functools.wraps(original)
    def __init__(self, *args, **kwargs):
        kwargs["creationflags"] = creation_flags(int(kwargs.get("creationflags") or 0))
        original(self, *args, **kwargs)

    setattr(__init__, _MARK, True)
    subprocess.Popen.__init__ = __init__
