"""On Windows, the programs the engine runs open no console window.

The flag logic is checked everywhere; that the wrapper is installed and that
processes still run and return their output is checked on Windows, where the
checks run the engine's tests too.
"""

import subprocess
import sys

import app  # noqa: F401  (importing the engine installs the wrapper on Windows)
import pytest
from app.windows_console import _MARK, CREATE_NEW_CONSOLE, CREATE_NO_WINDOW, DETACHED_PROCESS, creation_flags


def test_a_process_gets_no_window_unless_it_asks_for_a_console():
    assert creation_flags(0) == CREATE_NO_WINDOW
    assert creation_flags(0x200) == 0x200 | CREATE_NO_WINDOW, "other flags are kept"
    assert creation_flags(CREATE_NEW_CONSOLE) == CREATE_NEW_CONSOLE
    assert creation_flags(DETACHED_PROCESS) == DETACHED_PROCESS


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_on_windows_every_process_starts_without_a_window_and_still_runs():
    assert getattr(subprocess.Popen.__init__, _MARK, False), "the wrapper is installed when the engine is imported"
    run = subprocess.run([sys.executable, "-c", "print('ran')"], capture_output=True, text=True, check=True)
    assert run.stdout.strip() == "ran"
    with subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdout.write(sys.stdin.read())"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    ) as process:
        out, _ = process.communicate("piped", timeout=60)
    assert out == "piped"


@pytest.mark.skipif(sys.platform == "win32", reason="elsewhere only")
def test_elsewhere_subprocess_is_left_alone():
    assert not getattr(subprocess.Popen.__init__, _MARK, False)


def test_the_wrapper_passes_the_flag_and_keeps_everything_else(monkeypatch):
    # Python refuses creation flags outside Windows, so the real Popen is swapped
    # for a recorder here; on Windows the test above starts real processes.
    from app import windows_console

    seen = []

    def recorder(self, *args, **kwargs):
        seen.append((args, kwargs))

    monkeypatch.setattr(subprocess.Popen, "__init__", recorder)
    windows_console.quiet_subprocesses()
    windows_console.quiet_subprocesses()  # a second install changes nothing
    subprocess.Popen(["ffmpeg", "-version"], stdout=subprocess.PIPE)
    subprocess.Popen(["cmd"], creationflags=CREATE_NEW_CONSOLE)
    assert seen[0] == ((["ffmpeg", "-version"],), {"stdout": subprocess.PIPE, "creationflags": CREATE_NO_WINDOW})
    assert seen[1][1]["creationflags"] == CREATE_NEW_CONSOLE
    assert len(seen) == 2, "wrapped once, not twice"
