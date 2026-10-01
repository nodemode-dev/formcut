"""formcut's planar tracker (P0 of DEV_PLAN_planar_tracking.md): a plane followed against its reference frame, in the
motion types Mocha names, on synthetic shots whose true corners are known (app/planar_bench.py). These run small, for
the checks; P0's bar is written at 1080p and is met there by the benchmark's command (see BUILD_NOTES)."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from app import planar, planar_bench
from app.planar import Settings, fit


def _transform(model: str) -> np.ndarray:
    a, s, tx, ty = 0.2, 1.3, 14.0, -9.0
    if model == "translation":
        return np.array([[1, 0, tx], [0, 1, ty], [0, 0, 1]], float)
    if model == "scale":
        return np.array([[s, 0, tx], [0, s, ty], [0, 0, 1]], float)
    if model == "similarity":
        return np.array([[s * np.cos(a), -s * np.sin(a), tx], [s * np.sin(a), s * np.cos(a), ty], [0, 0, 1]], float)
    if model == "affine":
        return np.array([[1.2, 0.3, tx], [-0.1, 0.9, ty], [0, 0, 1]], float)
    return np.array([[1.1, 0.2, tx], [-0.05, 0.95, ty], [0.0004, -0.0002, 1]], float)


@pytest.mark.parametrize("model", ["translation", "scale", "similarity", "affine", "perspective"])
def test_each_motion_model_recovers_its_transform_past_outliers(model):
    rng = np.random.default_rng(2)
    a = rng.uniform(0, 400, (200, 2))
    truth = _transform(model)
    b = cv2.perspectiveTransform(a.reshape(-1, 1, 2), truth).reshape(-1, 2)
    b[:40] += rng.uniform(-60, 60, (40, 2))  # a fifth of the points wrong, as an occluder makes them
    found, inliers = fit(model, a, b)
    assert found is not None and inliers[40:].mean() > 0.95
    probe = np.array([[0, 0], [400, 0], [400, 400], [0, 400]], float)
    got = cv2.perspectiveTransform(probe.reshape(-1, 1, 2), found).reshape(-1, 2)
    want = cv2.perspectiveTransform(probe.reshape(-1, 1, 2), truth).reshape(-1, 2)
    assert np.abs(got - want).max() < 0.05


def test_the_checked_motion_types_make_mochas_models():
    assert Settings().model() == "similarity"  # translation, scale and rotation: Mocha's defaults
    assert Settings(perspective=True).model() == "perspective"
    assert Settings(shear=True).model() == "affine"
    assert Settings(rotation=False).model() == "scale"
    assert Settings(scale=False, rotation=False).model() == "translation"


def _scenario(name: str, **changes) -> planar_bench.Scenario:
    return planar_bench.Scenario(**{**planar_bench.SCENARIOS[name].__dict__, **changes})


@pytest.mark.parametrize(
    ("name", "mean", "worst"),
    [
        ("moderate", 0.25, 0.6),
        ("strong", 0.35, 1.0),
        ("similarity", 0.2, 0.5),
        ("translation", 0.15, 0.4),
        ("blur-light", 0.4, 1.2),
    ],
)
def test_a_plane_is_followed_to_a_fraction_of_a_pixel(name, mean, worst):
    """640 x 360 over 60 frames; at 1080p the same shots hold 0.02 to 0.28 px mean (the benchmark's command)."""
    r = planar_bench.run(_scenario(name, frames=60))
    assert r["unoccludedMean"] < mean and r["unoccludedWorst"] < worst, r
    assert r["last10"] < r["first10"] * 3 + 0.1, r  # no drift


def test_an_occluder_is_tracked_through_and_better_when_excluded():
    plain = planar_bench.run(_scenario("occluded", frames=80))
    excluded = planar_bench.run(_scenario("excluded", frames=80))
    assert plain["occludedMean"] < 0.5 and excluded["occludedMean"] < 0.4, (plain, excluded)
    assert excluded["occludedMean"] <= plain["occludedMean"] + 0.02
    assert plain["last10"] < 0.3 and excluded["last10"] < 0.3  # it comes back clean after


def test_a_long_shot_does_not_drift():
    r = planar_bench.run(_scenario("moderate", frames=300, width=480, height=270))
    assert r["last10"] < r["first10"] * 2 + 0.05 and r["mean"] < 0.25, r


def test_tracking_backwards_from_the_last_frame():
    r = planar_bench.run(_scenario("moderate", frames=60), backwards=True)
    assert r["unoccludedMean"] < 0.25 and r["scenario"].endswith("(backwards)"), r


def test_a_faint_surface_holds_under_a_pixel():
    """The benchmark's hardest: a low-contrast surface drawn inside its edges. At 1080p its mean passes P0's bar (0.42
    px) and its worst frame is 1.54 px against 1.5: P0's one open item."""
    r = planar_bench.run(_scenario("low-texture", frames=60))
    assert r["unoccludedMean"] < 0.8 and r["unoccludedWorst"] < 2.0, r


def test_manual_motion_follows_the_prediction_without_tracking():
    frames, truth, _ = planar_bench.shot(_scenario("moderate", frames=4))
    matte = np.zeros(frames[0].shape[:2], np.uint8)
    cv2.fillPoly(matte, [truth[0].astype(np.int32)], 255)
    tracker = planar.PlanarTracker(frames[0], matte, Settings(perspective=True, motion="manual"))
    h, confidence = tracker.step(frames[1])
    assert confidence == 0.0 and np.allclose(h, np.eye(3))
