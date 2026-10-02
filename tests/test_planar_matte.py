"""A clip's tracked matte (P3 of the planar tracking plan, Mocha's Apply Matte): its planar layers' shapes, adding
and cutting, carried by their tracks to the clip's source frame, in the decoded picture's own pixels, feathered and
inverted on request; applied on every path (the device takes it as the mask alpha) and refused by the export graphs."""

from __future__ import annotations

import subprocess

import pytest
from app import fast_export, planar_bench
from app.durable import write_json
from app.planar_api import STORE
from app.render_document import validate_document
from app.renderer import FrameRenderer

W, H = 320, 180


@pytest.fixture
def plate(tmp_path):
    """A 20-frame video in the library (a benchmark shot: texture everywhere, so nothing in it is black)."""
    from app.media import ingest_path

    s = planar_bench.Scenario(**{**planar_bench.SCENARIOS["moderate"].__dict__, "frames": 20, "width": W, "height": H})
    frames, _, _ = planar_bench.shot(s)
    path = tmp_path / "plate.mkv"
    encode = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{W}x{H}",
            "-r",
            "30",
            "-i",
            "-",
            "-c:v",
            "ffv1",
            "-pix_fmt",
            "bgr0",
            str(path),
        ],
        stdin=subprocess.PIPE,
    )
    for frame in frames:
        encode.stdin.write(frame.tobytes())
    encode.stdin.close()
    assert encode.wait() == 0
    # the layer's track: two pixels to the right a frame
    STORE.mkdir(parents=True, exist_ok=True)
    write_json(
        STORE / "matte-layer.json",
        {
            "media": "x",
            "fps": 30.0,
            "size": [W, H],
            "reference": 0,
            "frames": {str(i): [1, 0, 2.0 * i, 0, 1, 0, 0, 0, 1] for i in range(20)},
            "confidence": {str(i): 1.0 for i in range(20)},
        },
    )
    return ingest_path(path, "plate.mkv")["id"]


def _render(media_id, matte, at):
    layer = {
        "id": "matte-layer",
        "shapes": [
            {"points": [[0.25, 0.25], [0.6, 0.25], [0.6, 0.75], [0.25, 0.75]], "mode": "add"},
            {"points": [[0.35, 0.4], [0.45, 0.4], [0.45, 0.6], [0.35, 0.6]], "mode": "subtract"},
        ],
        "reference": 0,
        "settings": {},
    }
    clip = {
        "id": "v",
        "kind": "video",
        "label": "plate",
        "start": 0,
        "duration": 20 / 30,
        "mediaId": media_id,
        "planar": {"version": 1, "layers": [layer]},
        "planarMatte": matte,
    }
    project = validate_document({"width": W, "height": H, "fps": 30, "activeTimeline": 0, "timelines": [{"tracks": [{"clips": [clip]}]}]})
    renderer = FrameRenderer(project, W)
    try:
        return renderer.frame(at)[:, :, :3].astype(int).sum(axis=2), project
    finally:
        renderer.close()


def test_the_matte_shows_the_clip_inside_its_shapes_only_and_follows_the_track(plate):
    shown, _ = _render(plate, {"layers": ["matte-layer"], "feather": 0, "invert": False}, 0.0)
    assert shown[90, 100] > 30 and shown[90, 170] > 30  # inside the added shape, either side of the hole (112-144 px)
    assert shown[90, 128] == 0 and shown[90, 40] == 0 and shown[20, 120] == 0  # the cut hole, and outside
    later, _ = _render(plate, {"layers": ["matte-layer"], "feather": 0, "invert": False}, 10 / 30)
    # after ten frames at 2 px a frame: the left edge from 80 px to 100, the hole from 112-144 px to 132-164
    assert later[90, 95] == 0 and later[90, 105] > 30
    assert later[90, 150] == 0 and later[90, 120] > 30


def test_the_matte_inverts_and_feathers(plate):
    inverted, _ = _render(plate, {"layers": ["matte-layer"], "feather": 0, "invert": True}, 0.0)
    assert inverted[90, 170] == 0 and inverted[90, 40] > 30 and inverted[90, 128] > 30
    hard, _ = _render(plate, {"layers": ["matte-layer"], "feather": 0, "invert": False}, 0.0)
    soft, _ = _render(plate, {"layers": ["matte-layer"], "feather": 4, "invert": False}, 0.0)
    assert soft[90, 78] > hard[90, 78] and soft[90, 84] < hard[90, 84]  # the edge at 80 px blurred both ways


def test_a_clip_with_a_tracked_matte_is_refused_by_the_export_graphs(plate):
    _, project = _render(plate, {"layers": ["matte-layer"], "feather": 0, "invert": False}, 0.0)
    assert "planarMatte" in fast_export.ABSENT and fast_export.refusal(project) is not None
