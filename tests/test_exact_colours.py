"""Exports take the faster layered graph by default; exact colours take the frame path.

On the owner's Mac (10 cores, the Rust kernels) the graph was 1.7x to 1.9x faster
than the frame path, and its colours identical or within 41 to 48 dB. The frame
path renders what the preview shows, so a person who needs the export to match it
exactly turns on exact colours in the export dialog.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest
from app.render_api import RenderInput

GRADE = {"exposure": 0.2, "contrast": 12, "saturation": 15}
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")


@pytest.fixture
def clip_id(tmp_path):
    from app import media

    clip = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=30:duration=2", "-pix_fmt", "yuv420p", str(clip)],
        check=True,
    )
    return media.ingest_path(clip, "clip.mp4")["id"]


def _export(clips, name, **options):
    from app.render_api import export_media
    from app.render_document import validate_document
    from conftest import make_project

    project = validate_document(make_project(width=320, height=180, fps=30, duration=1.0, clips=clips))
    return export_media(project, name, lambda f: None, lambda: False, "webm", "high", **options)["renderPath"]


def _graded(clip_id):
    return [{"id": "a", "kind": "video", "label": "a", "mediaId": clip_id, "start": 0, "duration": 1.0, "sourceIn": 0.0, "colour": GRADE}]


@needs_ffmpeg
def test_a_graded_clip_takes_the_faster_graph_by_default(clip_id, monkeypatch):
    monkeypatch.delenv("FORMCUT_EXPORT_PATH", raising=False)
    assert _export(_graded(clip_id), "default") == "layered"


@needs_ffmpeg
def test_exact_colours_take_the_frame_path(clip_id, monkeypatch):
    monkeypatch.delenv("FORMCUT_EXPORT_PATH", raising=False)
    assert _export(_graded(clip_id), "exact", exact=True) == "frames"


@needs_ffmpeg
def test_the_override_keeps_the_graph_even_for_exact_colours(clip_id, monkeypatch):
    monkeypatch.setenv("FORMCUT_EXPORT_PATH", "layered")
    assert _export(_graded(clip_id), "override", exact=True) == "layered"


@needs_ffmpeg
def test_a_plain_cut_stays_native_since_it_is_already_exact(clip_id, monkeypatch):
    monkeypatch.delenv("FORMCUT_EXPORT_PATH", raising=False)
    plain = [{"id": "a", "kind": "video", "label": "a", "mediaId": clip_id, "start": 0, "duration": 1.0, "sourceIn": 0.0}]
    assert _export(plain, "plain", exact=True) == "native"


def test_the_request_carries_exact_colours_off_by_default():
    assert RenderInput(project={}).exact is False
    assert RenderInput(project={}, exact=True).exact is True
