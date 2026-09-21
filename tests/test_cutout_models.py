"""Cutout models.

Most of these run everywhere, against stand-in ONNX sessions, because what they
check is formcut's own contract with each model: what it feeds, what it keeps
between calls, and what it chooses from the answer. The last few run the real
weights and skip where they have not been downloaded.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from app import model_manager, segmentation
from app.segmentation import CUTOUT_MODELS, VideoMatter, cutout_alpha, raw_alpha


@pytest.fixture(autouse=True)
def fresh_caches():
    segmentation._cache.clear()
    segmentation._embeddings.clear()
    yield
    segmentation._cache.clear()
    segmentation._embeddings.clear()


@pytest.fixture
def installed(monkeypatch):
    monkeypatch.setattr(segmentation, "ready", lambda model: True)


def picture(height: int = 64, width: int = 96, seed: int = 1) -> np.ndarray:
    return (np.random.default_rng(seed).random((height, width, 3)) * 255).astype(np.uint8)


class Session:
    """An ONNX Runtime session that answers from a function and remembers its feeds."""

    def __init__(self, names: list[str], answer):
        self.names, self.answer, self.feeds = names, answer, []

    def get_outputs(self):
        return [SimpleNamespace(name=name) for name in self.names]

    def run(self, names, feeds):
        self.feeds.append(feeds)
        result = self.answer(feeds)
        return [result[name] for name in (names or self.names)]


def test_every_cutout_model_is_a_registered_model():
    assert set(CUTOUT_MODELS) <= set(model_manager.MODELS)


def test_an_unknown_model_is_refused(installed):
    with pytest.raises(ValueError, match="Download the selected cutout model"):
        cutout_alpha(picture(), {"model": "local-speech"})


def test_a_model_that_is_not_downloaded_is_refused(monkeypatch):
    monkeypatch.setattr(segmentation, "ready", lambda model: False)
    with pytest.raises(ValueError, match="Download the selected cutout model"):
        cutout_alpha(picture(), {"model": "sharp-cutout"})


def test_point_selection_without_a_point_asks_for_one(installed):
    with pytest.raises(ValueError, match="Point at what to keep first"):
        raw_alpha(picture(), "click-select")


def test_a_raw_matte_is_the_models_own_answer(installed, monkeypatch):
    ramp = np.tile(np.linspace(0, 1, 96, dtype=np.float32), (64, 1))
    monkeypatch.setattr(segmentation, "_infer", lambda model, image, options: ramp)
    assert np.allclose(raw_alpha(picture(), "sharp-cutout"), ramp, atol=1e-6)


def test_the_threshold_and_feather_still_shape_a_cutout(installed, monkeypatch):
    ramp = np.tile(np.linspace(0, 1, 96, dtype=np.float32), (64, 1))
    monkeypatch.setattr(segmentation, "_infer", lambda model, image, options: ramp)
    shaped = cutout_alpha(picture(), {"model": "sharp-cutout", "threshold": 0.5, "feather": 0.1})
    assert shaped[0, 0] == 0 and shaped[0, -1] == 1


def test_the_same_frame_is_not_run_twice(installed, monkeypatch):
    runs = []
    monkeypatch.setattr(segmentation, "_infer", lambda model, image, options: runs.append(model) or np.zeros((8, 8), np.float32))
    image = picture()
    raw_alpha(image, "sharp-cutout")
    raw_alpha(image, "sharp-cutout")
    assert runs == ["sharp-cutout"]


def test_different_points_on_one_frame_are_different_answers(installed, monkeypatch):
    runs = []
    monkeypatch.setattr(
        segmentation, "_infer", lambda model, image, options: runs.append(options["points"]) or np.zeros((8, 8), np.float32)
    )
    image = picture()
    raw_alpha(image, "click-select", [{"x": 0.2, "y": 0.2}])
    raw_alpha(image, "click-select", [{"x": 0.8, "y": 0.8}])
    assert len(runs) == 2


def matting_session() -> Session:
    def answer(feeds):
        height, width = feeds["src"].shape[2:]
        return {
            "fgr": feeds["src"],
            "pha": np.full((1, 1, height, width), 0.7, np.float32),
            **{f"r{i}o": feeds[f"r{i}i"] + 1 for i in range(1, 5)},
        }

    return Session(["fgr", "pha", "r1o", "r2o", "r3o", "r4o"], answer)


def test_video_matting_starts_from_an_empty_state(monkeypatch):
    session = matting_session()
    monkeypatch.setattr(segmentation, "_session", lambda model, name=None: session)
    VideoMatter()(picture())
    assert all(float(session.feeds[0][f"r{i}i"].sum()) == 0 for i in range(1, 5))


def test_video_matting_carries_its_state_to_the_next_frame(monkeypatch):
    session = matting_session()
    monkeypatch.setattr(segmentation, "_session", lambda model, name=None: session)
    matter = VideoMatter()
    matter(picture())
    matter(picture(seed=2))
    assert all(float(session.feeds[1][f"r{i}i"].max()) == 1 for i in range(1, 5))


def test_video_matting_returns_its_matte_unstretched(monkeypatch):
    session = matting_session()
    monkeypatch.setattr(segmentation, "_session", lambda model, name=None: session)
    assert np.allclose(VideoMatter()(picture()), 0.7)


def test_video_matting_works_at_most_512_across_inside(monkeypatch):
    session = matting_session()
    monkeypatch.setattr(segmentation, "_session", lambda model, name=None: session)
    VideoMatter()(np.zeros((1080, 1920, 3), np.uint8))
    assert session.feeds[0]["downsample_ratio"][0] == pytest.approx(512 / 1920)


def test_a_small_frame_is_matted_at_full_size(monkeypatch):
    session = matting_session()
    monkeypatch.setattr(segmentation, "_session", lambda model, name=None: session)
    VideoMatter()(picture())
    assert session.feeds[0]["downsample_ratio"][0] == 1.0


def sam_sessions(scores=(0.9, 0.8, 0.5), areas=(10, 200, 400)) -> dict:
    encoder = Session(
        ["high_res_feats_0", "high_res_feats_1", "image_embed"],
        lambda feeds: {
            "high_res_feats_0": np.zeros((1, 32, 256, 256), np.float32),
            "high_res_feats_1": np.zeros((1, 64, 128, 128), np.float32),
            "image_embed": np.zeros((1, 256, 64, 64), np.float32),
        },
    )

    def answer(feeds):
        masks = np.full((1, 3, 256, 256), -10.0, np.float32)
        for index, area in enumerate(areas):
            masks[0, index].flat[:area] = 10.0
        return {"masks": masks, "iou_predictions": np.array([scores], np.float32)}

    return {segmentation.SAM_ENCODER: encoder, segmentation.SAM_DECODER: Session(["masks", "iou_predictions"], answer)}


def use(monkeypatch, sessions: dict) -> dict:
    monkeypatch.setattr(segmentation, "_session", lambda model, name=None: sessions[name])
    return sessions


def test_a_point_is_placed_in_the_encoders_1024_square(monkeypatch):
    sessions = use(monkeypatch, sam_sessions())
    segmentation._sam(picture(), [{"x": 0.5, "y": 0.25}])
    coords = sessions[segmentation.SAM_DECODER].feeds[0]["point_coords"]
    assert coords.tolist()[0][0] == [512.0, 256.0]


def test_the_points_end_with_the_padding_point_sam_expects(monkeypatch):
    sessions = use(monkeypatch, sam_sessions())
    segmentation._sam(picture(), [{"x": 0.5, "y": 0.5}])
    feeds = sessions[segmentation.SAM_DECODER].feeds[0]
    assert feeds["point_coords"].tolist()[0][-1] == [0.0, 0.0] and feeds["point_labels"].tolist()[0][-1] == -1.0


def test_a_point_marked_not_to_keep_is_a_background_point(monkeypatch):
    sessions = use(monkeypatch, sam_sessions())
    segmentation._sam(picture(), [{"x": 0.5, "y": 0.5}, {"x": 0.1, "y": 0.1, "keep": False}])
    assert sessions[segmentation.SAM_DECODER].feeds[0]["point_labels"].tolist()[0] == [1.0, 0.0, -1.0]


def test_one_click_takes_the_largest_plausible_mask(monkeypatch):
    use(monkeypatch, sam_sessions(scores=(0.9, 0.8, 0.5), areas=(10, 200, 400)))
    matte = segmentation._sam(np.zeros((256, 256, 3), np.uint8), [{"x": 0.5, "y": 0.5}])
    assert int((matte > 0.5).sum()) == 200


def test_several_points_take_the_best_scoring_mask(monkeypatch):
    use(monkeypatch, sam_sessions(scores=(0.9, 0.8, 0.5), areas=(10, 200, 400)))
    matte = segmentation._sam(np.zeros((256, 256, 3), np.uint8), [{"x": 0.5, "y": 0.5}, {"x": 0.6, "y": 0.5}])
    assert int((matte > 0.5).sum()) == 10


def test_a_frame_is_encoded_once_however_many_clicks(monkeypatch):
    sessions = use(monkeypatch, sam_sessions())
    image = picture()
    segmentation._sam(image, [{"x": 0.2, "y": 0.2}])
    segmentation._sam(image, [{"x": 0.7, "y": 0.4}])
    assert len(sessions[segmentation.SAM_ENCODER].feeds) == 1 and len(sessions[segmentation.SAM_DECODER].feeds) == 2


def test_the_matte_from_a_point_is_a_probability(monkeypatch):
    use(monkeypatch, sam_sessions())
    matte = segmentation._sam(picture(), [{"x": 0.5, "y": 0.5}])
    assert float(matte.min()) >= 0 and float(matte.max()) <= 1


def test_first_launch_never_fetches_copyleft_weights(monkeypatch):
    fetched = []
    monkeypatch.setattr(model_manager, "ready", lambda model: False)
    monkeypatch.setattr(
        model_manager, "_tracked", lambda model, report, cancelled: fetched.append(model) or {"model": model, "ready": True}
    )
    monkeypatch.setattr(model_manager, "hub_fetch", lambda model, path: None)
    model_manager.prepare(lambda fraction: None, lambda: False, True, True)
    assert "video-matting" not in fetched and "sharp-cutout" in fetched and "click-select" in fetched


def test_without_fetching_nothing_is_downloaded(monkeypatch):
    fetched = []
    monkeypatch.setattr(model_manager, "ready", lambda model: False)
    monkeypatch.setattr(model_manager, "_tracked", lambda model, report, cancelled: fetched.append(model) or {})
    model_manager.prepare(lambda fraction: None, lambda: False, False)
    assert fetched == []


def needs(model: str):
    return pytest.mark.skipif(not model_manager.ready(model), reason=f"{model} weights are not downloaded here")


def disc(size: int = 256) -> np.ndarray:
    image = np.full((size, size, 3), 30, np.uint8)
    rows, columns = np.ogrid[:size, :size]
    image[(rows - size / 2) ** 2 + (columns - size / 2) ** 2 < (size / 5) ** 2] = (240, 200, 60)
    return image


@needs("click-select")
def test_sam_selects_the_disc_it_is_pointed_at():
    matte = raw_alpha(disc(), "click-select", [{"x": 0.5, "y": 0.5}]) > 0.5
    inside = disc()[:, :, 0] == 240
    assert (matte & inside).sum() / max(1, (matte | inside).sum()) > 0.8


@needs("click-select")
def test_sam_pointed_outside_the_disc_leaves_it_out():
    matte = raw_alpha(disc(), "click-select", [{"x": 0.05, "y": 0.05}]) > 0.5
    assert not matte[128, 128]


@needs("sharp-cutout")
def test_isnet_finds_the_disc_more_than_the_ground():
    matte = raw_alpha(disc(), "sharp-cutout")
    inside = disc()[:, :, 0] == 240
    assert float(matte[inside].mean()) > float(matte[~inside].mean()) + 0.3


@needs("video-matting")
def test_rvm_answers_every_pixel_between_zero_and_one():
    matte = VideoMatter()(disc())
    assert matte.shape == (256, 256) and float(matte.min()) >= 0 and float(matte.max()) <= 1
