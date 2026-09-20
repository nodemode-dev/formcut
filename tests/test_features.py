"""The newer features, each checked against an input whose answer is known."""

from __future__ import annotations

import numpy as np
import pytest


def test_beats_are_found_at_a_known_tempo():
    from app.rhythm import beats

    rate, seconds = 48000, 8.0
    t = np.arange(int(rate * seconds)) / rate
    click = np.zeros_like(t)
    for n in range(16):  # a click every half second: 120 bpm
        at = int(n * 0.5 * rate)
        click[at : at + 600] += np.sin(2 * np.pi * 180 * t[:600]) * np.exp(-np.linspace(0, 8, 600))
    found = beats(click, rate)
    assert found["bpm"] == pytest.approx(120, abs=2)
    assert found["count"] >= 12
    assert found["beats"][0] == pytest.approx(0.5, abs=0.06)


def test_silence_has_no_beats():
    from app.rhythm import beats

    assert beats(np.zeros(48000, np.float32))["count"] == 0


def test_ducking_finds_speech_and_leaves_silence_alone():
    from app.rhythm import ducking

    rate = 48000
    speech = np.zeros(rate * 8, np.float32)
    rng = np.random.default_rng(5)
    speech[rate : int(rate * 2.5)] = rng.normal(0, 0.2, int(rate * 1.5))
    speech[rate * 5 : rate * 6] = rng.normal(0, 0.2, rate)
    result = ducking(speech, rate)
    assert len(result["regions"]) == 2
    assert result["regions"][0]["start"] == pytest.approx(1.0, abs=0.1)
    volumes = [frame["props"]["volume"] for frame in result["keyframes"]]
    assert min(volumes) == pytest.approx(0.25) and max(volumes) == pytest.approx(1.0)


def test_a_mask_follows_a_moving_subject(moving_frames):
    from app.subject import track_points

    mask = [
        {"x": 38 / 320, "y": 68 / 180},
        {"x": 82 / 320, "y": 68 / 180},
        {"x": 82 / 320, "y": 112 / 180},
        {"x": 38 / 320, "y": 112 / 180},
    ]
    path = track_points(moving_frames, mask)
    assert len(path) == len(moving_frames)
    moved = (path[-1]["points"][0]["x"] - path[0]["points"][0]["x"]) * 320
    assert moved == pytest.approx(72, abs=10), "the mask did not follow the subject"


def test_tracking_a_still_subject_keeps_the_mask_still():
    from app.subject import track_points

    rng = np.random.default_rng(2)
    still = [np.dstack([(rng.random((180, 320)) * 255).astype(np.uint8)] * 3)] * 6
    mask = [{"x": 0.3, "y": 0.3}, {"x": 0.6, "y": 0.3}, {"x": 0.6, "y": 0.6}, {"x": 0.3, "y": 0.6}]
    path = track_points(still, mask)
    assert abs(path[-1]["points"][0]["x"] - 0.3) < 0.02


def test_reframe_follows_the_subject(moving_frames):
    from app.subject import reframe

    result = reframe(moving_frames, 9 / 16)
    assert result["crops"][-1]["x"] > result["crops"][0]["x"]
    assert 0 <= result["crops"][0]["x"] <= 1


def test_filler_words_are_found_and_nothing_else_is():
    from app.subject import fillers

    result = fillers([{"start": 0.0, "end": 4.0, "text": "So um I was basically going to like say something"}])
    assert {item["word"] for item in result["ranges"]} >= {"um", "basically", "like"}
    assert result["seconds"] > 0


def test_a_clean_sentence_has_no_fillers():
    from app.subject import fillers

    assert fillers([{"start": 0, "end": 2, "text": "The result is ready"}])["count"] == 0


def test_scene_detection_finds_a_hard_cut(tmp_path):
    from app.scenes import scenes as find_scenes

    path = tmp_path / "cut.mp4"
    import subprocess

    from app.tools import ffmpeg

    made = subprocess.run(
        [
            ffmpeg(),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=160x90:d=2",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=160x90:d=2",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1[v]",
            "-map",
            "[v]",
            "-r",
            "15",
            str(path),
        ],
        capture_output=True,
        check=False,
        timeout=120,
    )
    if made.returncode != 0 or not path.is_file():
        pytest.skip("no ffmpeg available to build the sample")
    cuts = find_scenes(path, 0.5)["cuts"]
    assert any(abs(float(cut["at"]) - 2.0) < 0.4 for cut in cuts), "the cut at two seconds was missed"


def test_a_colour_grade_at_neutral_changes_nothing():
    from app.pixel_effects import COLOUR_PANEL, colour_panel

    rng = np.random.default_rng(3)
    image = rng.random((60, 80, 3)).astype(np.float32)
    assert np.abs(colour_panel(image.copy(), dict(COLOUR_PANEL)) - image).max() < 1e-6


def test_an_effect_turned_off_changes_nothing():
    from app.pixel_effects import apply_effects

    rng = np.random.default_rng(6)
    image = (rng.random((60, 80, 4)) * 255).astype(np.uint8)
    off = apply_effects(image.copy(), [{"id": "gaussian", "amount": 0, "params": {"radius": 6}}], 0.5)
    assert np.array_equal(off, image)


def test_an_effect_at_full_amount_changes_the_picture():
    from app.pixel_effects import apply_effects

    rng = np.random.default_rng(6)
    image = (rng.random((60, 80, 4)) * 255).astype(np.uint8)
    on = apply_effects(image.copy(), [{"id": "gaussian", "amount": 1, "params": {"radius": 6}}], 0.5)
    assert not np.array_equal(on, image)


def test_pointing_at_one_thing_keeps_only_that_thing():
    """A matte with two objects, and a click choosing between them."""
    import numpy as np
    from app.segmentation import pick_region, region_count

    matte = np.zeros((180, 320), np.float32)
    matte[40:120, 30:90] = 1.0  # left
    matte[40:120, 200:280] = 1.0  # right
    assert region_count(matte) == 2

    left = pick_region(matte, 60 / 320, 80 / 180)
    right = pick_region(matte, 240 / 320, 80 / 180)
    assert left[:, 160:].sum() == 0, "pointing left kept something on the right"
    assert right[:, :160].sum() == 0, "pointing right kept something on the left"
    assert left.sum() > 0 and right.sum() > 0


def test_pointing_at_the_background_still_keeps_something():
    """An empty result looks exactly like a broken tool, so it takes the nearest."""
    import numpy as np
    from app.segmentation import pick_region

    matte = np.zeros((180, 320), np.float32)
    matte[40:120, 30:90] = 1.0
    assert pick_region(matte, 0.5, 0.95).sum() > 0
