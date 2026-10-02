"""Screen replacement with its glare kept (the owner's phone shots): where the screen is comes from a tracked outline,
not a key; the reflection on it is measured from the channels the screen does not give and goes over the new screen as
neutral light; what is in front of the screen stays; the screen's light on what is near it is replaced by the new
screen's colour. A key alone left the glare green, the edges ragged under it, and a finger lit green."""

from __future__ import annotations

import numpy as np
from app.render_document import validate_document
from app.renderer import CPU_STEPS, FrameRenderer
from PIL import Image


def _render(tmp_path, spec, extra=None):
    from app.media import ingest_path

    plate = np.zeros((200, 400, 3), np.uint8)
    plate[:] = (116, 186, 198)  # the teal wall
    plate[30:170, 90:310] = (12, 12, 12)  # the phone's bezel
    plate[40:160, 100:300] = (10, 245, 10)  # the screen
    plate[60:100, 120:170] = (170, 255, 170)  # glare on it: the screen's green with white light over it
    plate[90:150, 250:280] = (190, 205, 150)  # a finger over the screen, lit green by it
    path = tmp_path / "plate.png"
    Image.fromarray(plate).save(path)
    layer = {
        "id": "screen",
        "shapes": [{"points": [[100 / 400, 40 / 200], [300 / 400, 40 / 200], [300 / 400, 160 / 200], [100 / 400, 160 / 200]]}],
        "reference": 0,
        "settings": {},
    }
    clip = {
        "id": "p",
        "kind": "image",
        "label": "plate",
        "start": 0,
        "duration": 1,
        "mediaId": ingest_path(path, "plate.png")["id"],
        "planar": {"version": 1, "layers": [layer]},
        "screenReplace": spec,
        **(extra or {}),
    }
    project = validate_document(
        {"width": 400, "height": 200, "fps": 30, "activeTimeline": 0, "timelines": [{"tracks": [{"clips": [clip]}]}]}
    )
    renderer = FrameRenderer(project, 400)
    try:
        return renderer.frame(0.5)[:, :, :3].astype(int)
    finally:
        renderer.close()


SPEC = {"layer": "screen", "screen": "green", "light": "#3040c0", "feather": 0.5}


def test_the_screen_goes_and_its_glare_stays_as_neutral_light(tmp_path):
    out = _render(tmp_path, SPEC)
    assert out[130, 150].max() <= 6  # the clean screen: nothing of it left over what lies below (black here)
    glare = out[80, 145]
    assert glare.min() > 120 and glare.max() - glare.min() <= 6  # the glare kept, neutral: no green in it


def test_what_is_in_front_stays_and_is_lit_by_the_new_screen_not_green(tmp_path):
    out = _render(tmp_path, SPEC)
    finger = out[120, 265]
    assert finger[0] > 150  # still there, in front
    assert finger[1] <= max(finger[0], finger[2]) + 2  # the green light taken off it
    assert finger[2] > 150  # and the new screen's blue light put on it (it was 150)


def test_the_bezel_and_the_wall_are_left_as_they_were(tmp_path):
    out = _render(tmp_path, SPEC)
    assert np.abs(out[35, 200] - [12, 12, 12]).max() <= 2
    assert np.abs(out[10, 10] - [116, 186, 198]).max() <= 2
    assert "screenReplace" in CPU_STEPS
