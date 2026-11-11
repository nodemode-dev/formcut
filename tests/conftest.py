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


def pytest_sessionfinish(session, exitstatus):
    if _OWN_DATA_DIR:
        import shutil

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
