"""100 and 120 fps projects, the rates the format sheet now offers beside 24 to 60, play and export at their own rate.

Playback streams at the lesser of the rate asked for and the project's, so a 100 fps project asked for at 100 must
send a frame every hundredth of a second; an export must write that many frames, stamped at that rate.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid

import pytest
from app.main import app
from app.render_stream import RAW_HEADER
from conftest import make_project, text_clip
from fastapi.testclient import TestClient

client = TestClient(app, headers={"x-formcut-local": "1"})
RATES = [100, 120]


@pytest.mark.parametrize("fps", RATES)
def test_the_document_takes_the_rate(fps):
    from app.render_document import validate_document

    assert validate_document(make_project(fps=fps))["fps"] == fps


@pytest.mark.parametrize("fps", RATES)
def test_playback_streams_on_the_projects_frame_grid(fps):
    seconds = 2.0
    project = make_project(fps=fps, duration=seconds, clips=[text_clip(duration=seconds)])
    session = client.post("/api/render/sessions", json={"project": project, "width": 320}).json()["id"]
    try:
        with client.stream("GET", f"/api/render/sessions/{session}/stream?start=0&fps={fps}&format=raw") as reply:
            assert reply.status_code == 200
            body = reply.read()
    finally:
        client.delete(f"/api/render/sessions/{session}")
    times, at = [], 0
    while at + RAW_HEADER.size <= len(body):
        size, time, _, _ = RAW_HEADER.unpack_from(body, at)
        times.append(time)
        at += RAW_HEADER.size + size
    # The stream keeps to the wall clock and skips frames when the renderer falls behind it (the first frame also
    # builds the renderer), so how many arrive depends on the machine. What does not: each one sits on the project's
    # own grid, in order, and the grid is not 60's, which a stream capped at 60 would use.
    assert len(times) >= 10, times
    assert times == sorted(set(times))
    assert all(abs(t * fps - round(t * fps)) < 1e-6 and t < seconds for t in times), times[:5]
    assert any(abs(t * 60 - round(t * 60)) > 1e-6 for t in times)


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg and ffprobe")
@pytest.mark.parametrize("fps", RATES)
def test_an_export_writes_every_frame_at_the_projects_rate(fps):
    from app.render_api import export_media

    project = make_project(width=320, height=180, fps=fps, duration=0.5, clips=[text_clip(duration=0.5)])
    result = export_media(project, "rates-" + uuid.uuid4().hex, lambda _: None, lambda: False, "mp4", "draft")
    command = ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_streams", "-of", "json", result["file"]]
    stream = json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)["streams"][0]
    assert stream["avg_frame_rate"] == f"{fps}/1"
    assert int(stream["nb_read_frames"]) == fps // 2
