"""Shared fixtures.

Everything here builds its own material from generated colour, tone and text so
a test never depends on a file being present, on a network, or on a model being
downloaded. A test that needs one of those skips itself and says so, rather than
failing and teaching people to ignore red.
"""

from __future__ import annotations

import os
import sys
import tempfile
import types
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
# The suite's own data folder, removed when the run ends (a full run leaves up to
# 150 MB of media, proxies and renders). A folder given in FORMCUT_DATA_DIR is kept.
_OWN_DATA_DIR = None if "FORMCUT_DATA_DIR" in os.environ else tempfile.mkdtemp(prefix="formcut-tests-")
os.environ.setdefault("FORMCUT_NO_WARM", "1")
if _OWN_DATA_DIR:
    os.environ["FORMCUT_DATA_DIR"] = _OWN_DATA_DIR
AGENT_STAND_INS = ("claude", "codex", "cursor-agent", "agy")
_AGENT_SANDBOX = Path(tempfile.mkdtemp(prefix="formcut-agents-"))
AGENT_CALLS = _AGENT_SANDBOX / "calls.log"
_REAL_HOME = Path.home()
_agent_calls: list[str] = []
if os.name == "posix":
    (_AGENT_SANDBOX / "bin").mkdir()
    for _name in AGENT_STAND_INS:
        (_AGENT_SANDBOX / "bin" / _name).write_text(
            f'#!/bin/sh\necho "{_name} $*" >> "{AGENT_CALLS}"\nif [ "$1" = "--version" ]; then echo "0.0.0 (stand-in)"; exit 0; fi\nexit 1\n'
        )
        (_AGENT_SANDBOX / "bin" / _name).chmod(0o755)
    (_AGENT_SANDBOX / "sh").write_text(
        '#!/bin/sh\nfor word in "$@"; do if [ "$found" = 1 ]; then exec /bin/sh -c "$word"; fi; if [ "$word" = "-c" ]; then found=1; fi; done\nexec /bin/sh\n'
    )
    (_AGENT_SANDBOX / "sh").chmod(0o755)
    os.environ["SHELL"] = str(_AGENT_SANDBOX / "sh")
    os.environ["PATH"] = os.pathsep.join(
        [str(_AGENT_SANDBOX / "bin")]
        + [
            folder
            for folder in os.environ.get("PATH", "").split(os.pathsep)
            if folder and not any((Path(folder) / name).exists() for name in (*AGENT_STAND_INS, "agent"))
        ]
    )
    for _name in ("NPM_CONFIG_PREFIX", "npm_config_prefix", "PNPM_HOME", "VOLTA_HOME", "BUN_INSTALL", "NVM_SYMLINK"):
        os.environ.pop(_name, None)
    for _name in ("CLAUDE", "CODEX", "CURSOR", "ANTIGRAVITY"):
        os.environ.pop(f"FORMCUT_{_name}_BIN", None)


@pytest.fixture(autouse=True)
def only_stand_in_agent_programs(monkeypatch):
    """Every test finds the stand-ins above and nothing else: no system install folder, and nothing under the real home folder."""
    from app import agent_lookup

    real = agent_lookup.candidates
    monkeypatch.setattr(agent_lookup, "system_folders", lambda platform=None: [])
    monkeypatch.setattr(
        agent_lookup,
        "candidates",
        lambda *given, **named: [place for place in real(*given, **named) if not place.is_relative_to(_REAL_HOME)],
    )
    agent_lookup.forget()


def pytest_terminal_summary(terminalreporter):
    terminalreporter.write_line(
        f"agent program stand-ins started {len(_agent_calls)} time(s): " + (", ".join(sorted(set(_agent_calls))) or "none")
    )


def window_headers() -> dict:
    """The window's headers: the fixed one and this launch's window key."""
    from app import window_key

    return {"x-formcut-local": "1", window_key.HEADER: window_key.KEY}


def _as_the_window(headers):
    if headers and dict(headers).get("x-formcut-local") == "1":
        return {**dict(headers), **window_headers()}
    return headers


def _clients_made_as_the_window_carry_the_key() -> None:
    """A test client made with, or a request sent with, the window's fixed header stands for the window, so it carries the key as well."""
    from fastapi.testclient import TestClient

    made, sent = TestClient.__init__, TestClient.request

    def init(self, *args, headers=None, **kwargs):
        made(self, *args, headers=_as_the_window(headers), **kwargs)

    def request(self, *args, headers=None, **kwargs):
        return sent(self, *args, headers=_as_the_window(headers), **kwargs)

    TestClient.__init__, TestClient.request = init, request
    TestClient.bare_request = sent


def bare(client):
    """The client as any local program: what it sends is exactly what the test gives it."""
    client.request = types.MethodType(type(client).bare_request, client)
    return client


_clients_made_as_the_window_carry_the_key()


def pytest_sessionfinish(session, exitstatus):
    import shutil

    if AGENT_CALLS.is_file():
        _agent_calls.extend(AGENT_CALLS.read_text(encoding="utf-8").splitlines())
    shutil.rmtree(_AGENT_SANDBOX, ignore_errors=True)
    if _OWN_DATA_DIR:
        shutil.rmtree(_OWN_DATA_DIR, ignore_errors=True)


TEXT = {"content": "FORMCUT", "size": 14, "color": "#ffcc55", "bold": True, "align": "center"}


def make_project(*, width=320, height=180, fps=30, duration=4.0, clips=None, background=None) -> dict:
    document = {
        "title": "test",
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "activeTimeline": 0,
        "timelines": [
            {
                "id": "tl",
                "name": "main",
                "tracks": [{"id": "t0", "name": "V", "clips": clips if clips is not None else [text_clip()]}],
            }
        ],
    }
    if background:
        document["background"] = background
    return document


def text_clip(*, clip_id="a", start=0.0, duration=4.0, **extra) -> dict:
    return {"id": clip_id, "kind": "text", "label": "t", "start": start, "duration": duration, "textStyle": dict(TEXT), **extra}


@pytest.fixture
def project() -> dict:
    return make_project()


@pytest.fixture
def tone() -> np.ndarray:
    """Two seconds of a 440 Hz tone at 48 kHz."""
    t = np.arange(48000 * 2) / 48000
    return (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)


@pytest.fixture
def moving_frames() -> list[np.ndarray]:
    """A textured square crossing the frame, eight pixels a frame."""
    rng = np.random.default_rng(4)
    patch = (rng.random((40, 40)) * 255).astype(np.uint8)
    frames = []
    for index in range(10):
        frame = np.zeros((180, 320), np.uint8)
        frame[70:110, 40 + index * 8 : 80 + index * 8] = patch
        frames.append(np.dstack([frame] * 3))
    return frames


# Checks that compare two decoders pixel for pixel: OpenCV's own ffmpeg, which the
# frame path reads through, against the system ffmpeg the native and layered paths
# run. Like the golden frames in checks.yml they are pinned to Linux, where CI
# controls both builds; Homebrew's newer major release rounds a little differently,
# which says nothing about formcut's code. They run on every Linux check.
DECODER_PARITY = pytest.mark.skipif(sys.platform != "linux", reason="compares two ffmpeg builds; pinned to Linux, where CI controls both")


def lgpl_ffmpeg(tmp_path, monkeypatch, tail=""):
    """An ffmpeg on PATH that behaves like the LGPL build the desktop app ships: libx264 and libx265 are neither
    listed nor accepted. `tail` replaces the real encode, to stand for an ffmpeg that fails."""
    import shutil

    from app import encoders

    real = shutil.which("ffmpeg")
    folder = tmp_path / "lgpl-bin"
    folder.mkdir()
    script = folder / "ffmpeg"
    refuse = 'for a in "$@"; do case "$a" in libx264|libx265) echo "Unknown encoder $a" >&2; exit 8;; esac; done\n'
    unlisted = f'case " $* " in *" -encoders "*) "{real}" "$@" | grep -v "libx26[45]"; exit 0;; esac\n'
    script.write_text("#!/bin/sh\n" + refuse + unlisted + (tail or f'exec "{real}" "$@"\n'), encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(encoders, "_detected", None)
    return folder
