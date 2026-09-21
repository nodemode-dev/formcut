"""Filmstrips on the timeline.

Every filmstrip request for a video failed with a TypeError: the proxy lookup
was called with the media id alone, and it needs the source and a size too. A
timeline with video clips therefore never showed its frames.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest
from app import clip_visuals, proxies


def clip(folder) -> object:
    path = folder / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=2", "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )
    return path


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg makes the clip")
def test_a_filmstrip_is_made_for_a_video(tmp_path):
    strip = tmp_path / "strip.jpg"
    assert clip_visuals._strip(clip(tmp_path), strip, "video", 2.0, 4)
    assert strip.is_file() and strip.stat().st_size > 0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg makes the clip")
def test_the_proxy_lookup_gets_the_source_and_the_strips_size(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(proxies, "usable", lambda media_id, source, decode_limit: asked.append((media_id, source, decode_limit)))
    source = clip(tmp_path)
    clip_visuals._strip(source, tmp_path / "strip.jpg", "video", 2.0, 4)
    assert asked == [("clip", source, clip_visuals.STRIP_WIDTH)]
