"""Every control an effect shows changes the picture, and its default is what renders.

Pixelate has its pixel size, LED Wall its LED size, Kaleidoscope its segments:
each declared parameter is rendered at its lowest and its highest and must give
a different picture. An untouched control renders its default, so the slider,
the clip and the thumbnail agree. The catalogue route lists the looks, and the
transition thumbnails render without a renderer instance.
"""

import numpy as np
import pytest
from app import effect_packages, pixel_effects
from app.catalogue import EFFECT_DEFAULTS, VIDEO_EFFECTS, catalogue, clamp_params, declare
from app.effect_previews import render

CONTROLLED = [(effect, d) for effect in VIDEO_EFFECTS for d in declare(EFFECT_DEFAULTS.get(effect, {}), effect)]


def _frame():
    rng = np.random.default_rng(3)
    y, x = np.mgrid[:90, :160].astype(np.float32)
    frame = np.dstack([x / 160, y / 90, 0.5 + 0.4 * np.sin(x / 9) * np.cos(y / 7)]) + rng.normal(0, 0.06, (90, 160, 3))
    frame[20:70, 40:120] = frame[20:70, 40:120] * 0.3 + np.array([0.86, 0.63, 0.52]) * 0.7
    return np.clip(frame, 0, 1).astype(np.float32)


@pytest.mark.parametrize(("effect", "declaration"), CONTROLLED, ids=[f"{e}.{d['key']}" for e, d in CONTROLLED])
def test_each_control_changes_the_picture(effect, declaration):
    # Some effects flicker by design (interference), so several moments are tried.
    for moment in (0.13, 0.8, 1.7):
        low = pixel_effects.process(_frame(), effect, moment, clamp_params({declaration["key"]: declaration["min"]}))
        high = pixel_effects.process(_frame(), effect, moment, clamp_params({declaration["key"]: declaration["max"]}))
        if np.abs(np.clip(low, 0, 1) - np.clip(high, 0, 1)).mean() > 1e-4:
            return
    pytest.fail(f"{effect}'s {declaration['key']} changes nothing between {declaration['min']} and {declaration['max']}")


def test_most_effects_have_controls_and_the_labels_say_what_they_do():
    assert sum(1 for e in VIDEO_EFFECTS if EFFECT_DEFAULTS.get(e)) >= 60
    labels = {e: {d["key"]: d["labelKey"] for d in declare(EFFECT_DEFAULTS.get(e, {}), e)} for e in ("pixelate", "led-wall", "halftone")}
    assert labels == {"pixelate": {"size": "param.pixelSize"}, "led-wall": {"size": "param.ledSize"}, "halftone": {"size": "param.dotSize"}}


@pytest.mark.parametrize("effect", ["oil-paint", "hex-pixelate", "led-wall", "bayer-dither", "kaleidoscope", "snowfall"])
def test_an_untouched_control_renders_its_default(effect):
    frame = np.round(_frame() * 255).astype(np.uint8)
    untouched = pixel_effects.apply_effects(frame.copy(), [{"id": effect, "amount": 1}], 0.8)
    stated = pixel_effects.apply_effects(frame.copy(), [{"id": effect, "amount": 1, "params": dict(EFFECT_DEFAULTS[effect])}], 0.8)
    assert np.array_equal(untouched, stated)


def test_the_catalogue_route_lists_the_looks():
    effect_packages.reload()  # as the engine does when it starts
    looks = [entry for entry in catalogue()["video"] if entry.get("group") == "Looks"]
    assert len(looks) == 180 and looks[0]["names"]


@pytest.mark.parametrize("kind", ["clock-wipe", "blinds", "diagonal-wipe", "diamond", "barn-door", "pixel-dissolve", "spin"])
def test_every_transition_thumbnail_renders(kind):
    assert render("transition", kind).ndim == 3
