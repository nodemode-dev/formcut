"""The chroma key's spill suppression and its tracked hold-out matte (P7 of the planar tracking plan): the key colour's
cast taken off what the key leaves, brightness kept; inside a hold-out's tracked shapes the key takes nothing away."""

from __future__ import annotations

import numpy as np
from app.render_document import validate_document
from app.renderer import FrameRenderer
from PIL import Image

W, H = 200, 100


def _render(tmp_path, key, planar=None):
    from app.media import ingest_path

    picture = np.zeros((H, W, 3), np.uint8)
    picture[:, :100] = (0, 200, 0)  # the green screen
    picture[:, 100:] = (200, 190, 120)  # a subject with green spilled on it
    picture[40:60, 150:] = (200, 40, 40)  # a red part, leaning away from green
    path = tmp_path / "plate.png"
    Image.fromarray(picture).save(path)
    clip = {
        "id": "c",
        "kind": "image",
        "label": "plate",
        "start": 0,
        "duration": 1,
        "mediaId": ingest_path(path, "plate.png")["id"],
        "key": key,
    }
    if planar:
        clip["planar"] = planar
    project = validate_document({"width": W, "height": H, "fps": 30, "activeTimeline": 0, "timelines": [{"tracks": [{"clips": [clip]}]}]})
    renderer = FrameRenderer(project, W)
    try:
        return renderer.frame(0.5)[:, :, :3].astype(int)
    finally:
        renderer.close()


KEY = {"color": "#00c800", "similarity": 0.25, "blend": 0.05}


def test_spill_suppression_takes_the_green_cast_off_and_keeps_brightness(tmp_path):
    plain = _render(tmp_path, KEY)
    cleaned = _render(tmp_path, {**KEY, "spill": 1.0})
    assert plain[50, 50].sum() == 0 and cleaned[50, 50].sum() == 0  # the screen keyed out either way
    before, after = plain[20, 104], cleaned[20, 104]  # beside the screen, where its spill is
    assert before[1] - after[1] > 15  # the green cast taken off the subject
    assert abs(before.mean() - after.mean()) < 3  # its brightness kept
    assert after[0] > before[0] and after[2] > before[2]
    assert np.abs(plain[50, 180] - cleaned[50, 180]).max() <= 1  # a red that leans away from green left alone


def test_a_tracked_hold_out_keeps_its_part_of_the_screen(tmp_path):
    layer = {
        "id": "keep",
        "shapes": [{"points": [[0.05, 0.1], [0.3, 0.1], [0.3, 0.9], [0.05, 0.9]], "mode": "add"}],
        "reference": 0,
        "settings": {},
    }
    held = _render(tmp_path, {**KEY, "holdout": ["keep"]}, {"version": 1, "layers": [layer]})
    assert held[50, 30][1] > 150  # inside the hold-out: the green kept
    assert held[50, 80].sum() == 0  # the rest of the screen keyed out
    assert held[20, 120][0] > 150  # the subject as before


def test_spill_or_a_hold_out_keeps_the_key_on_this_side():
    assert FrameRenderer._device_resident({"key": KEY}, []) is True
    assert FrameRenderer._device_resident({"key": {**KEY, "spill": 0.5}}, []) is False
    assert FrameRenderer._device_resident({"key": {**KEY, "holdout": ["a"]}}, []) is False


def test_the_key_command_and_the_inspector_keep_spill_and_the_hold_out():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "frontend" / "src"
    project = (root / "engine" / "project.ts").read_text(encoding="utf-8")
    assert "spill: Math.min(1, Math.max(0, p.key.spill))" in project and "holdout: p.key.holdout.filter" in project
    inspector = (root / "ui" / "inspector-pane.ts").read_text(encoding="utf-8")
    assert '"keySpill"' in inspector and "spill, holdout }" in inspector


def test_spill_fades_with_distance_from_what_the_key_took(tmp_path):
    """Spill is the screen's light, near it: a green-leaning colour far from the keyed screen keeps its hue (on the
    owner's clip 10 a teal wall far from the phone turned blue when spill was taken off everywhere)."""
    from app.media import ingest_path

    picture = np.zeros((300, 1200, 3), np.uint8)
    picture[:, :100] = (0, 200, 0)  # a narrow screen at the left
    picture[:, 100:] = (60, 140, 140)  # teal: leans towards green a little
    path = tmp_path / "teal.png"
    Image.fromarray(picture).save(path)
    clip = {
        "id": "c",
        "kind": "image",
        "label": "teal",
        "start": 0,
        "duration": 1,
        "mediaId": ingest_path(path, "teal.png")["id"],
        "key": {**KEY, "spill": 1.0},
    }
    project = validate_document(
        {"width": 1200, "height": 300, "fps": 30, "activeTimeline": 0, "timelines": [{"tracks": [{"clips": [clip]}]}]}
    )
    renderer = FrameRenderer(project, 1200)
    try:
        out = renderer.frame(0.5)[:, :, :3].astype(int)
    finally:
        renderer.close()
    assert np.abs(out[150, 1100] - [60, 140, 140]).max() <= 2  # a thousand pixels away: its own colour
    assert out[150, 105][1] < 135  # beside the screen: the green lean taken off
