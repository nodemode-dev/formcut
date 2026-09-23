import sys

if sys.platform == "win32":
    # Before any engine module can start a process: see windows_console.py.
    from .windows_console import quiet_subprocesses

    quiet_subprocesses()
