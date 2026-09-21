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
os.environ.setdefault("FORMCUT_DATA_DIR", tempfile.mkdtemp(prefix="formcut-tests-"))

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
