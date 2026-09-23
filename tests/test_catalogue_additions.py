"""The effects and transitions added in 1.35.0: each does something, the same way twice.

Effects run where preview and export both run them, so a moving effect has to be
seeded from the clip's time: the same moment must give the same picture. Every
transition has to begin fully out and end fully in.
"""

import numpy as np
import pytest
from app import pixel_effects
from app.catalogue import EFFECT_DEFAULTS, TRANSITIONS, VIDEO_EFFECTS, label
from app.renderer import FrameRenderer

NEW_EFFECTS = VIDEO_EFFECTS[VIDEO_EFFECTS.index("chroma-noise") + 1 :]
NEW_TRANSITIONS = TRANSITIONS[TRANSITIONS.index("push-up") + 1 :]


def _frame():
    # Gradients, fine texture and a skin-toned patch, so that effects which act
    # only on detail (clarity) or only on skin (skin smoothing) have work to do.
    y, x = np.mgrid[:90, :160].astype(np.float32)
    frame = np.dstack([x / 160, y / 90, 0.5 + 0.4 * np.sin(x / 9) * np.cos(y / 7)])
    frame[20:70, 40:120] = (0.86, 0.63, 0.52)
    texture = np.random.default_rng(3).normal(0, 0.06, frame.shape)
    return np.clip(frame + texture, 0, 1).astype(np.float32)


def test_the_catalogue_grew_as_described():
    assert len(NEW_EFFECTS) == 18 and len(VIDEO_EFFECTS) == 76
    assert len(NEW_TRANSITIONS) == 11 and len(TRANSITIONS) == 23
    assert label("vhs-tape") == "VHS Tape" and label("clock-wipe") == "Clock Wipe"


@pytest.mark.parametrize("effect", NEW_EFFECTS)
def test_each_new_effect_changes_the_picture_the_same_way_twice(effect):
    frame, params = _frame(), dict(EFFECT_DEFAULTS.get(effect, {}))
    first = pixel_effects.process(frame.copy(), effect, 0.8, dict(params))
    again = pixel_effects.process(frame.copy(), effect, 0.8, dict(params))
    assert first.shape == frame.shape and np.isfinite(first).all()
    assert np.array_equal(first, again), "the same moment must render the same picture"
    assert np.abs(np.clip(first, 0, 1) - frame).mean() > 0.002, "the effect left the picture unchanged"


def _layer():
    layer = np.zeros((60, 80, 4), np.uint8)
    layer[:, :, 0], layer[:, :, 3] = 200, 255
    return layer


@pytest.mark.parametrize("kind", NEW_TRANSITIONS)
def test_each_new_transition_begins_out_and_ends_in(kind):
    worker = FrameRenderer.__new__(FrameRenderer)
    incoming = {"transitionIn": {"type": kind}, "transitionLength": 1.0}
    start = worker.transition(_layer(), incoming, 0.0)
    shown = start[:, :, 3].astype(bool) & (start[:, :, 0] > 0)
    assert shown.mean() < 0.02, "the incoming clip should not show at the start"
    end = worker.transition(_layer(), incoming, 0.999)
    assert (end[:, :, 3] > 200).mean() > 0.9, "the incoming clip should be in at the end"
    outgoing = {"transitionOut": {"type": kind, "length": 1.0}, "duration": 2.0}
    assert np.array_equal(worker.transition_out(_layer(), outgoing, 1.5), _layer()), "before its band the outgoing clip is untouched"
