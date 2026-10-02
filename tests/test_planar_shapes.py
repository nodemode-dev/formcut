"""Planar layers as roto (P5 of the planar tracking plan): keyframed shapes, X-Splines with each point's tension,
each point's own feather, and Link to Track, as the engine, the renderer and the workspace all draw them."""

from __future__ import annotations

import numpy as np
from app.planar_shapes import layer_matte, outline, points_at

SQUARE = [[0.3, 0.3], [0.7, 0.3], [0.7, 0.7], [0.3, 0.7]]


def test_keyframed_points_run_linearly_between_keys_and_hold_beyond():
    shape = {"points": SQUARE, "keys": {"10": SQUARE, "20": [[x + 0.1, y] for x, y in SQUARE]}}
    assert np.allclose(points_at(shape, 15)[0], [0.35, 0.3])
    assert np.allclose(points_at(shape, 0)[0], [0.3, 0.3]) and np.allclose(points_at(shape, 99)[0], [0.4, 0.3])
    assert np.allclose(points_at({"points": SQUARE}, 7), SQUARE)


def test_an_xspline_is_straight_at_no_tension_and_curves_at_full():
    sharp, _ = outline(np.array(SQUARE), {"kind": "xspline", "tension": [0, 0, 0, 0]})
    smooth, _ = outline(np.array(SQUARE), {"kind": "xspline", "tension": [1, 1, 1, 1]})
    top_sharp = sharp[(np.abs(sharp[:, 0] - 0.5) < 0.02) & (sharp[:, 1] < 0.5)]
    top_smooth = smooth[(np.abs(smooth[:, 0] - 0.5) < 0.02) & (smooth[:, 1] < 0.5)]
    assert np.allclose(top_sharp[:, 1], 0.3, atol=1e-6)  # a corner at every point: the sides straight
    assert (top_smooth[:, 1] < 0.29).all()  # a smooth curve through the corners bulges past the side
    plain, where = outline(np.array(SQUARE), {"kind": "polygon"})
    assert np.allclose(plain, SQUARE) and list(where) == [0, 1, 2, 3]


def test_each_point_feathers_its_own_part_of_the_edge():
    w = h = 200
    shape = {"points": SQUARE, "feather": [0, 20, 20, 0]}  # the right side soft, the left hard

    def carry(pts):
        return pts * [w, h]

    matte = layer_matte([shape], 0, carry, (w, h), lambda pts: pts)
    assert matte[100, 100] == 1.0
    assert 0.3 < matte[100, 140 + 10] < 0.7  # 10 px outside the right side, half way through its 20 px feather
    assert matte[100, 60 - 10] == 0  # 10 px outside the left side: no feather there
    hard = layer_matte([{"points": SQUARE}], 0, carry, (w, h), lambda pts: pts)
    assert hard[100, 150] == 0


def test_a_linked_roto_layer_rides_another_layers_track_with_its_own_keys(tmp_path):
    """The renderer's tracked matte: layer B has no track of its own; linked to A, it moves with A's track (2 px a
    frame), and its own keyframes change its shape on top."""
    import subprocess

    from app import planar_bench
    from app.durable import write_json
    from app.media import ingest_path
    from app.planar_api import STORE
    from app.render_document import validate_document
    from app.renderer import FrameRenderer

    s = planar_bench.Scenario(**{**planar_bench.SCENARIOS["moderate"].__dict__, "frames": 20, "width": 320, "height": 180})
    frames, _, _ = planar_bench.shot(s)
    path = tmp_path / "roto.mkv"
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
            "320x180",
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
    media_id = ingest_path(path, "roto.mkv")["id"]
    STORE.mkdir(parents=True, exist_ok=True)
    write_json(
        STORE / "carrier.json",
        {
            "media": media_id,
            "fps": 30.0,
            "size": [320, 180],
            "reference": 0,
            "frames": {str(i): [1, 0, 2.0 * i, 0, 1, 0, 0, 0, 1] for i in range(20)},
            "confidence": {},
        },
    )
    roto = {
        "id": "roto",
        "link": "carrier",
        "shapes": [{"points": SQUARE, "keys": {"0": SQUARE, "10": [[0.3, 0.3], [0.8, 0.3], [0.8, 0.7], [0.3, 0.7]]}}],
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
        "planar": {"version": 1, "layers": [roto]},
        "planarMatte": {"layers": ["roto"], "feather": 0, "invert": False},
    }
    project = validate_document(
        {"width": 320, "height": 180, "fps": 30, "activeTimeline": 0, "timelines": [{"tracks": [{"clips": [clip]}]}]}
    )

    def shown(at):
        renderer = FrameRenderer(project, 320)
        try:
            return renderer.frame(at)[:, :, :3].astype(int).sum(axis=2)
        finally:
            renderer.close()

    first, tenth = shown(0.0), shown(10 / 30)
    assert first[90, 100] > 30 and first[90, 230] == 0  # the square, 96 to 224 px, at frame 0
    # at frame 10: carried 20 px right by A's track (116 px), its right side keyed out to 0.8 (256 + 20 = 276 px)
    assert tenth[90, 105] == 0 and tenth[90, 125] > 30 and tenth[90, 260] > 30 and tenth[90, 285] == 0
