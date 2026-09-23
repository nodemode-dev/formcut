"""The effects browser's mask and cutout cards: every shape, and the presets.

Each mask thumbnail is drawn from the renderer's own polygon, so a card shows the
mask it applies; each cutout preset is either a model at given edge settings or
the colour key, and its thumbnail shapes a stand-in matte with the engine's own
edge formula.
"""

import numpy as np
from app.catalogue import CUTOUT_PRESETS, catalogue
from app.effect_previews import MASKS, known, render
from app.renderer import MASK_SHAPES


def test_every_mask_shape_but_the_pen_has_a_card_and_a_thumbnail():
    assert set(MASKS) == set(MASK_SHAPES) | {"linear"} and len(MASKS) >= 12
    for shape in MASKS:
        assert known("mask", shape) and render("mask", shape)[:, :, 3].any()


def test_the_triangle_and_pentagon_stand_on_a_side():
    for shape in ("triangle", "pentagon"):
        top = min(MASK_SHAPES[shape], key=lambda point: point[1])
        assert abs(top[0] - 0.5) < 1e-6 and abs(top[1]) < 1e-6


def test_at_least_twelve_cutout_presets_each_with_its_own_thumbnail():
    assert len(CUTOUT_PRESETS) >= 12 and catalogue()["cutouts"] == CUTOUT_PRESETS
    pictures = {render("cutout", preset["id"]).tobytes() for preset in CUTOUT_PRESETS}
    assert len(pictures) == len(CUTOUT_PRESETS), "two presets draw the same thumbnail"
    for preset in CUTOUT_PRESETS:
        assert ("key" in preset) != ("model" in preset)
        if "model" in preset:
            assert preset["model"] in ("person-cutout", "object-cutout") and 0 <= preset["threshold"] <= 1 and preset["feather"] > 0


def test_a_tighter_preset_keeps_less_of_the_subject():
    # Thumbnails are composited over the dark card, so how much of the bright
    # subject survives shows as brightness, not alpha.
    def kept(preset_id):
        return float(np.asarray(render("cutout", preset_id))[:, :, :3].mean())

    assert kept("person-tight") < kept("person-standard") < kept("person-loose")
