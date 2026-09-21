"""One media file at two moments at once: each keeps its own read position.

A picture in picture of the same shot, or a crossfade within one file, used to
pull a single decoder back and forth, restarting ffmpeg on almost every frame.
"""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg and ffprobe")


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    from app import media
    from conftest import make_project

    clip = tmp_path_factory.mktemp("cursors") / "clip.mp4"
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=160x90:rate=30:duration=3",
        "-pix_fmt",
        "yuv420p",
        str(clip),
    ]
    subprocess.run(command, check=True)
    media_id = media.ingest_path(clip, "clip.mp4")["id"]

    def video(clip_id, start, duration, source_in, **extra):
        return {
            "id": clip_id,
            "kind": "video",
            "label": clip_id,
            "mediaId": media_id,
            "start": start,
            "duration": duration,
            "sourceIn": source_in,
            **extra,
        }

    document = make_project(width=160, height=90, fps=30, duration=1.5, clips=[video("a", 0, 1.5, 0.0)])
    picture = video("p", 0.2, 1.3, 1.0, transform={"scale": 40, "x": 20, "y": -15})
    document["timelines"][0]["tracks"].append({"id": "t1", "name": "V", "clips": [picture]})
    return document


def test_two_moments_of_one_file_decode_without_restarting(project, monkeypatch):
    from app import video_source
    from app.renderer import FrameRenderer

    starts = []
    original = video_source.VideoSource._start
    monkeypatch.setattr(video_source.VideoSource, "_start", lambda self: (starts.append(self.requested), original(self))[1])
    renderer = FrameRenderer(project)
    try:
        for index in range(40):
            renderer.frame(index / 30)
    finally:
        renderer.close()
    assert len(starts) <= 2, starts


def test_the_frames_are_the_ones_a_fresh_seek_gives(project):
    from app.renderer import FrameRenderer

    renderer = FrameRenderer(project)
    try:
        sequential = [renderer.frame(index / 30) for index in range(0, 40, 3)]
    finally:
        renderer.close()
    for position, index in enumerate(range(0, 40, 3)):
        fresh = FrameRenderer(project)
        try:
            assert np.array_equal(np.asarray(fresh.frame(index / 30)), np.asarray(sequential[position])), index
        finally:
            fresh.close()
