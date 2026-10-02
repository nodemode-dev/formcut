"""Screen replacement as the owner asked for it after the phone shots: tracked mattes drawn as anti-aliased vector
paths (a whole-pixel fill stepped along every edge); the screen cut out by its tracked outline, a key only for what is
in front of it; the screen's reflection as light of its own for the Screen blend (the plate's own washed pixels left
over the picture read as a grey film)."""

from __future__ import annotations

import cv2
import numpy as np
from app.planar_green import screen_outline
from app.planar_shapes import layer_matte
from app.render_document import validate_document
from app.renderer import CPU_STEPS, FrameRenderer
from PIL import Image

SLANT = [[0.21, 0.18], [0.77, 0.23], [0.74, 0.83], [0.18, 0.79]]


def test_a_tracked_matte_is_an_anti_aliased_path():
    matte = layer_matte([{"points": SLANT}], 0, lambda pts: pts * [400, 300], (400, 300), lambda pts: pts)
    edge = (matte > 0.02) & (matte < 0.98)
    assert edge.sum() > 400  # its slanted sides drawn with partial pixels, not steps
    assert matte[150, 200] == 1.0 and matte[5, 5] == 0.0


def _plate(tmp_path):
    from app.media import ingest_path

    plate = np.zeros((300, 400, 3), np.uint8)
    plate[:] = (116, 186, 198)  # the teal wall
    cv2.fillPoly(plate, [np.round(np.array(SLANT) * [400, 300]).astype(np.int32)], (12, 12, 12))  # bezel outline below
    screen = np.array([[0.24, 0.22], [0.74, 0.27], [0.71, 0.79], [0.21, 0.75]])
    cv2.fillPoly(plate, [np.round(screen * [400, 300]).astype(np.int32)], (10, 245, 10))
    plate[90:130, 120:170] = (170, 250, 170)  # glare: the screen's green with white light over it
    plate[150:200, 220:250] = (190, 205, 150)  # a finger over the screen, lit green by it
    plate[160:190, 120:160] = (222, 248, 220)  # the glare's hottest part: the screen's lead all but gone
    path = tmp_path / "plate.png"
    Image.fromarray(plate).save(path)
    layer = {"id": "screen", "shapes": [{"points": screen.round(6).tolist()}], "reference": 0, "settings": {}}
    return ingest_path(path, "plate.png")["id"], layer


def _render(tmp_path, field, spec):
    media, layer = _plate(tmp_path)
    clip = {
        "id": "p",
        "kind": "image",
        "label": "plate",
        "start": 0,
        "duration": 1,
        "mediaId": media,
        "planar": {"version": 1, "layers": [layer]},
        field: spec,
    }
    project = validate_document(
        {"width": 400, "height": 300, "fps": 30, "activeTimeline": 0, "timelines": [{"tracks": [{"clips": [clip]}]}]}
    )
    renderer = FrameRenderer(project, 400)
    try:
        return renderer.frame(0.5)[:, :, :3].astype(int)
    finally:
        renderer.close()


def test_the_screen_is_cut_by_its_outline_and_what_is_in_front_stays(tmp_path):
    out = _render(tmp_path, "screenCut", {"layer": "screen", "screen": "green"})
    assert out[200, 150].max() <= 3 and out[110, 145].max() <= 3  # the screen and its glare gone (black below)
    assert out[175, 140].max() <= 3  # its hottest part too
    finger = out[175, 235]
    assert finger[0] > 150 and finger[1] <= max(finger[0], finger[2]) + 2  # the finger kept, its green taken off
    assert np.abs(out[10, 10] - [116, 186, 198]).max() <= 2  # the wall
    assert "screenCut" in CPU_STEPS and "glare" in CPU_STEPS


def test_the_glare_is_light_of_its_own_on_the_screen_only(tmp_path):
    out = _render(tmp_path, "glare", {"layer": "screen", "screen": "green", "strength": 1.0, "smooth": 3})
    glare = out[110, 145]
    assert glare.min() > 80 and glare.max() - glare.min() <= 2  # neutral light where the reflection is
    assert out[200, 150].max() <= 12  # the clean screen: next to none
    assert out[175, 235].max() <= 12 and out[10, 10].max() == 0  # nothing on the finger, nothing off the screen


def test_a_screens_outline_is_traced_as_a_smooth_path():
    frame = np.full((360, 640, 3), (198, 186, 116), np.uint8)
    cv2.rectangle(frame, (190, 50), (450, 310), (12, 12, 12), -1)
    flat = np.zeros((360, 640), np.uint8)
    cv2.rectangle(flat, (230, 60), (410, 300), 255, -1)
    cv2.rectangle(flat, (200, 90), (440, 270), 255, -1)
    for cx, cy in ((230, 90), (410, 90), (230, 270), (410, 270)):
        cv2.circle(flat, (cx, cy), 30, 255, -1)
    frame[flat > 0] = (0, 245, 0)
    outline = screen_outline(frame)
    assert outline is not None and len(outline) == 480
    assert abs(outline[:, 0].min() - 199.5) < 0.6 and abs(outline[:, 0].max() - 440.5) < 0.6
    assert abs(outline[:, 1].min() - 59.5) < 0.6 and abs(outline[:, 1].max() - 300.5) < 0.6


def test_the_edge_band_never_cuts_what_is_in_front(tmp_path):
    """A fingertip crossing the screen's edge keeps its outline: the band where the path alone decides the edge spares
    what is clearly in front (skin is uneven in red and blue; the bezel and the screen's green are not)."""
    from app.media import ingest_path

    plate = np.zeros((300, 400, 3), np.uint8)
    plate[:] = (12, 12, 12)
    plate[60:240, 80:320] = (10, 245, 10)  # the screen
    plate[40:80, 180:220] = (205, 160, 130)  # a fingertip across the screen's top edge (y = 60)
    path = tmp_path / "edge.png"
    Image.fromarray(plate).save(path)
    layer = {"id": "screen", "shapes": [{"points": [[0.2, 0.2], [0.8, 0.2], [0.8, 0.8], [0.2, 0.8]]}], "reference": 0, "settings": {}}
    clip = {
        "id": "p",
        "kind": "image",
        "label": "edge",
        "start": 0,
        "duration": 1,
        "mediaId": ingest_path(path, "edge.png")["id"],
        "planar": {"version": 1, "layers": [layer]},
        "screenCut": {"layer": "screen", "screen": "green"},
    }
    project = validate_document(
        {"width": 400, "height": 300, "fps": 30, "activeTimeline": 0, "timelines": [{"tracks": [{"clips": [clip]}]}]}
    )
    renderer = FrameRenderer(project, 400)
    try:
        out = renderer.frame(0.5)[:, :, :3].astype(int)
    finally:
        renderer.close()
    assert out[62, 200][0] > 180  # the fingertip just inside the screen's edge, in the band: kept
    assert out[150, 200].max() <= 3  # the screen: gone
