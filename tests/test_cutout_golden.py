"""Golden mattes, the prompts SAM 2 is given, and the checks every cutout passes first.

The golden mattes were made by each model from the same drawn picture, so a
change that shifts what a model is fed or how its answer is read shows up as a
different matte. They run where the weights are downloaded and skip elsewhere;
point FORMCUT_MODELS_DIR at the weights to run them.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from app import model_manager, segmentation
from app.segmentation import prompts, raw_alpha
from app.validation import clip_values

GOLDEN = Path(__file__).parent / "golden"
BOX = {"x0": 0.25, "y0": 0.25, "x1": 0.75, "y1": 0.75}


@pytest.fixture(autouse=True)
def fresh_caches():
    segmentation._cache.clear()
    segmentation._embeddings.clear()
    yield
    segmentation._cache.clear()
    segmentation._embeddings.clear()


def disc(size: int = 256) -> np.ndarray:
    image = np.full((size, size, 3), 30, np.uint8)
    rows, columns = np.ogrid[:size, :size]
    image[(rows - size / 2) ** 2 + (columns - size / 2) ** 2 < (size / 5) ** 2] = (240, 200, 60)
    return image


def agrees(matte: np.ndarray, name: str) -> bool:
    expected = cv2.imread(str(GOLDEN / f"{name}.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
    overlap = ((matte > 0.5) & (expected > 0.5)).sum() / max(1, ((matte > 0.5) | (expected > 0.5)).sum())
    return overlap >= 0.97 and float(np.abs(matte - expected).mean()) <= 0.02


def needs(model: str):
    return pytest.mark.skipif(not model_manager.ready(model), reason=f"{model} weights are not downloaded here")


@needs("object-cutout")
def test_u2net_small_matches_its_golden_matte():
    assert agrees(raw_alpha(disc(), "object-cutout"), "u2netp-disc")


@needs("sharp-cutout")
def test_isnet_matches_its_golden_matte():
    assert agrees(raw_alpha(disc(), "sharp-cutout"), "isnet-disc")


@needs("click-select")
def test_sam2_from_a_point_matches_its_golden_matte():
    assert agrees(raw_alpha(disc(), "click-select", [{"x": 0.5, "y": 0.5}]), "sam2-point-disc")


@needs("click-select")
def test_sam2_from_a_box_matches_its_golden_matte():
    assert agrees(raw_alpha(disc(), "click-select", None, BOX), "sam2-box-disc")


@needs("click-select")
def test_a_sam2_clip_renders_with_the_point_the_inspector_stores(tmp_path):
    from app import media
    from app.render_document import validate_document
    from app.renderer import FrameRenderer

    still = tmp_path / "disc.png"
    cv2.imwrite(str(still), cv2.cvtColor(disc(), cv2.COLOR_RGB2BGR))
    record = media.ingest_path(still, "disc.png")
    cutout = {"model": "click-select", "point": {"x": 0.5, "y": 0.5}, "threshold": 0.5, "feather": 0.1}
    clip = {"id": "c", "kind": "image", "label": "d", "mediaId": record["id"], "start": 0, "duration": 1, "cutout": cutout}
    track = {"id": "v", "name": "V", "clips": [clip]}
    project = {"title": "t", "width": 256, "height": 256, "fps": 30, "activeTimeline": 0, "background": "#0000ff"}
    frame = FrameRenderer(validate_document({**project, "timelines": [{"id": "t", "name": "m", "tracks": [track]}]})).frame(0.5)
    assert tuple(frame[128, 128, :3]) == (240, 200, 60) and tuple(frame[5, 5, :3]) == (0, 0, 255)


def test_the_single_point_the_inspector_stores_is_a_prompt():
    assert prompts({"point": {"x": 0.3, "y": 0.4}}) == ([{"x": 0.3, "y": 0.4}], None)


def test_a_list_of_points_wins_over_the_single_point():
    assert prompts({"point": {"x": 0.1, "y": 0.1}, "points": [{"x": 0.5, "y": 0.5}]})[0] == [{"x": 0.5, "y": 0.5}]


def test_a_box_is_a_prompt():
    assert prompts({"box": BOX}) == ([], BOX)


def test_nothing_given_is_no_prompt():
    assert prompts({}) == ([], None)


def test_entries_that_are_not_points_are_ignored():
    assert prompts({"points": ["here", {"x": 0.5, "y": 0.5}]})[0] == [{"x": 0.5, "y": 0.5}]


def test_a_box_alone_is_enough_for_sam(monkeypatch):
    asked = []
    monkeypatch.setattr(segmentation, "_sam", lambda image, points, box=None: asked.append((points, box)) or np.zeros((4, 4), np.float32))
    segmentation._infer("click-select", disc(), {"box": BOX})
    assert asked == [([], BOX)]


def test_a_box_reaches_sam_as_two_corners_without_padding(monkeypatch):
    feeds = []

    def session(model, name=None):
        if name == segmentation.SAM_ENCODER:
            answer = {"high_res_feats_0": 0, "high_res_feats_1": 0, "image_embed": 0}
            return SimpleNamespace(run=lambda names, feeds_: [answer[n] for n in names])
        masks = np.zeros((1, 3, 8, 8), np.float32)
        return SimpleNamespace(run=lambda names, given: feeds.append(given) or [masks, np.array([[0.9, 0.5, 0.1]], np.float32)])

    monkeypatch.setattr(segmentation, "_session", session)
    segmentation._sam(disc(), [], BOX)
    assert feeds[0]["point_coords"].tolist() == [[[256.0, 256.0], [768.0, 768.0]]]
    assert feeds[0]["point_labels"].tolist() == [[2.0, 3.0]]


def cutout_clip(**cutout) -> dict:
    return {"id": "c", "kind": "video", "start": 0, "duration": 1, "cutout": {"model": "click-select", **cutout}}


@pytest.mark.parametrize("model", segmentation.CUTOUT_MODELS)
def test_every_model_segmentation_runs_passes_validation(model):
    clip_values({"id": "c", "kind": "video", "start": 0, "duration": 1, "cutout": {"model": model}})


def test_an_unknown_cutout_model_is_refused():
    with pytest.raises(ValueError, match="Unknown cutout model"):
        clip_values(cutout_clip(model="teleport"))


def test_points_inside_the_frame_pass():
    clip_values(cutout_clip(points=[{"x": 0.2, "y": 0.8}, {"x": 0.5, "y": 0.5, "keep": False}]))


def test_a_point_outside_the_frame_is_refused():
    with pytest.raises(ValueError):
        clip_values(cutout_clip(points=[{"x": 1.5, "y": 0.5}]))


def test_more_than_sixteen_points_are_refused():
    with pytest.raises(ValueError, match="at most 16"):
        clip_values(cutout_clip(points=[{"x": 0.5, "y": 0.5}] * 17))


def test_a_box_inside_the_frame_passes():
    clip_values(cutout_clip(box=BOX))


def test_a_box_without_a_size_is_refused():
    with pytest.raises(ValueError, match="a size"):
        clip_values(cutout_clip(box={"x0": 0.5, "y0": 0.5, "x1": 0.5, "y1": 0.8}))


def test_a_box_outside_the_frame_is_refused():
    with pytest.raises(ValueError):
        clip_values(cutout_clip(box={"x0": 0.2, "y0": 0.2, "x1": 1.4, "y1": 0.8}))


def test_a_frozen_build_serves_the_locales_it_carries(monkeypatch, tmp_path):
    import sys

    from app import main

    folder = tmp_path / "frontend_dist" / "locales"
    folder.mkdir(parents=True)
    (folder / "zz.json").write_text(json.dumps({"app.title": "formcut"}), encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert "zz" in json.dumps(main.locales())
