"""A graded single clip exports through the exact frame path, measured as fast as the graph.

Everything wider keeps the layered graph, since only this case was measured.
"""

from __future__ import annotations

import dataclasses
import shutil
import subprocess
from pathlib import Path

import pytest
from app import fast_layers, pixel_effects
from app.fast_layers import Layer, Plan

GRADE = {"exposure": 0.2, "contrast": 12, "saturation": 15}
KERNEL = pixel_effects._native_colour() is not None


def one(**change) -> Plan:
    layer = Layer(
        source=Path("clip.mp4"),
        rate=30.0,
        width=320,
        height=180,
        seek=0.0,
        shift=0.0,
        span=1.0,
        first=0,
        frames=30,
        lead=0.0,
        duration=1.0,
        x=0,
        y=0,
        w=320,
        h=180,
        flip_h=False,
        flip_v=False,
        opacity=1.0,
        fade_in=0.0,
        fade_out=0.0,
        grade={"colour": GRADE, "lutId": None, "lutIntensity": 1},
    )
    return Plan(width=320, height=180, fps=30, count=30, background=(0, 0, 0), layers=[dataclasses.replace(layer, **change)])


def test_a_full_frame_graded_video_prefers_the_exact_path_where_the_kernel_is_built():
    assert fast_layers.prefers_exact(one()) is KERNEL


@pytest.mark.parametrize(
    "change",
    [
        {"grade": None},
        {"grade": {"colour": GRADE, "lutId": "look", "lutIntensity": 1}},
        {"grade": {"colour": {**GRADE, "sharpen": 20}, "lutId": None, "lutIntensity": 1}},
        {"fade_in": 0.5},
        {"fade_out": 0.5},
        {"opacity": 0.8},
        {"angle": 90.0},
        {"flip_h": True},
        {"x": 10, "w": 160, "h": 90},
        {"still": True},
    ],
)
def test_anything_the_measurement_did_not_cover_keeps_the_graph(change):
    assert fast_layers.prefers_exact(one(**change)) is False


def test_two_layers_keep_the_graph():
    plan = one()
    plan.layers.append(plan.layers[0])
    assert fast_layers.prefers_exact(plan) is False


def test_without_the_kernel_the_graph_is_kept(monkeypatch):
    monkeypatch.setattr(pixel_effects, "_native_colour", lambda: None)
    assert fast_layers.prefers_exact(one()) is False


@pytest.mark.skipif(not (KERNEL and shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg and the native kernel")
def test_an_export_takes_the_exact_path_and_the_override_keeps_the_graph(tmp_path, monkeypatch):
    from app import media
    from app.render_api import export_media
    from app.render_document import validate_document
    from conftest import make_project

    clip = tmp_path / "clip.mp4"
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x180:rate=30:duration=2",
        "-pix_fmt",
        "yuv420p",
        str(clip),
    ]
    subprocess.run(command, check=True)
    media_id = media.ingest_path(clip, "clip.mp4")["id"]
    graded = {"id": "a", "kind": "video", "label": "a", "mediaId": media_id, "start": 0, "duration": 1.0, "sourceIn": 0.0, "colour": GRADE}
    project = validate_document(make_project(width=320, height=180, fps=30, duration=1.0, clips=[graded]))
    monkeypatch.delenv("FORMCUT_EXPORT_PATH", raising=False)
    assert export_media(project, "exact", lambda f: None, lambda: False, "webm", "high")["renderPath"] == "frames"
    monkeypatch.setenv("FORMCUT_EXPORT_PATH", "layered")
    assert export_media(project, "graph", lambda f: None, lambda: False, "webm", "high")["renderPath"] == "layered"
