"""SAM 2.1 following a subject through a clip, and the matte job that runs it.

The contract tests use stand-in graphs to check what the tracker feeds each
graph: the seed frame's prompt, the later frames' padding point, the memory
bank's shape and temporal rows, the pointer offsets. The matte job tests check
that a trimmed clip's mattes land at its own source times and that tracking
runs forward and then backward from the frame the prompt was made on. The last
test runs the real weights where they are downloaded.
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from app import model_manager, sam_video

ROWS = np.arange(7 * 64, dtype=np.float32).reshape(7, 64)


class Graph:
    def __init__(self, names, answer):
        self.names, self.answer, self.feeds = names, answer, []

    def get_outputs(self):
        return [SimpleNamespace(name=name) for name in self.names]

    def run(self, names, feeds):
        self.feeds.append(feeds)
        result = self.answer(feeds)
        return [result[name] for name in (names or self.names)]


@pytest.fixture
def graphs(monkeypatch) -> dict:
    zeros = np.zeros
    made = {
        "vision_encoder": Graph(
            ["feats0", "feats1", "feats2", "feats2_no_mem", "vision_pos_embed"],
            lambda f: {
                "feats0": zeros((1, 32, 256, 256), np.float32),
                "feats1": zeros((1, 64, 128, 128), np.float32),
                "feats2": zeros((1, 256, 64, 64), np.float32),
                "feats2_no_mem": np.ones((1, 256, 64, 64), np.float32),
                "vision_pos_embed": zeros((1, 256, 64, 64), np.float32),
            },
        ),
        "mask_decoder": Graph(
            ["low_res_mask", "high_res_mask", "iou", "object_score_logits", "object_pointer"],
            lambda f: {
                "low_res_mask": zeros((1, 1, 256, 256), np.float32),
                "high_res_mask": np.full((1, 1, 1024, 1024), 5.0, np.float32),
                "iou": np.ones((1, 1), np.float32),
                "object_score_logits": np.ones((1, 1, 1), np.float32),
                "object_pointer": np.full((1, 1, 256), len(made["mask_decoder"].feeds), np.float32),
            },
        ),
        "memory_encoder": Graph(
            ["memory_tokens", "memory_pos"],
            lambda f: {"memory_tokens": zeros((4096, 1, 64), np.float32), "memory_pos": zeros((4096, 1, 64), np.float32)},
        ),
        "memory_attention": Graph(["conditioned_feats"], lambda f: {"conditioned_feats": np.full((1, 256, 64, 64), 2.0, np.float32)}),
        "pointer_tpos": Graph(["pointer_pos"], lambda f: {"pointer_pos": np.repeat(f["normalized_diffs"][:, None], 64, axis=1)}),
    }
    constants = {
        "image_size": 1024,
        "image_mean": [0.485, 0.456, 0.406],
        "image_std": [0.229, 0.224, 0.225],
        "memory_temporal_positional_encoding": ROWS.tolist(),
        "num_maskmem": 7,
        "max_object_pointers": 16,
    }
    monkeypatch.setattr(sam_video, "_session", lambda name: made[name])
    monkeypatch.setattr(sam_video, "_constants", lambda: constants)
    return made


def picture() -> np.ndarray:
    return np.zeros((90, 160, 3), np.uint8)


def test_the_seed_frame_is_decoded_from_the_prompt_on_its_memoryless_features(graphs):
    sam_video.VideoTracker([{"x": 0.5, "y": 0.25}], None, 10)(picture())
    feeds = graphs["mask_decoder"].feeds[0]
    assert feeds["input_points"].tolist() == [[[[512.0, 256.0]]]] and feeds["input_labels"].tolist() == [[[1]]]
    assert float(feeds["feats2_cond"].mean()) == 1.0


def test_the_seed_frame_becomes_a_binarized_conditioning_memory(graphs):
    sam_video.VideoTracker([{"x": 0.5, "y": 0.5}], None, 10)(picture())
    assert float(graphs["memory_encoder"].feeds[0]["binarize"]) == 1.0


def test_a_box_is_given_as_two_corners_labelled_two_and_three(graphs):
    sam_video.VideoTracker([], {"x0": 0.25, "y0": 0.25, "x1": 0.75, "y1": 0.5}, 10)(picture())
    feeds = graphs["mask_decoder"].feeds[0]
    assert feeds["input_points"].tolist() == [[[[256.0, 256.0], [768.0, 512.0]]]] and feeds["input_labels"].tolist() == [[[2, 3]]]


def test_a_later_frame_is_decoded_from_memory_with_only_a_padding_point(graphs):
    tracker = sam_video.VideoTracker([{"x": 0.5, "y": 0.5}], None, 10)
    tracker(picture())
    tracker(picture())
    feeds = graphs["mask_decoder"].feeds[1]
    assert feeds["input_labels"].tolist() == [[[-1]]] and float(feeds["feats2_cond"].mean()) == 2.0
    assert float(graphs["memory_encoder"].feeds[1]["binarize"]) == 0.0


def test_the_bank_is_seven_blocks_and_sixteen_pointers(graphs):
    tracker = sam_video.VideoTracker([{"x": 0.5, "y": 0.5}], None, 10)
    for _ in range(3):
        tracker(picture())
    feeds = graphs["memory_attention"].feeds[-1]
    assert feeds["memory"].shape == (28736, 1, 64) and feeds["memory_pos"].shape == (28736, 1, 64)


def test_each_memory_carries_its_temporal_row(graphs):
    tracker = sam_video.VideoTracker([{"x": 0.5, "y": 0.5}], None, 10)
    for _ in range(4):
        tracker(picture())
    pos = graphs["memory_attention"].feeds[-1]["memory_pos"]
    rows = [pos[block * 4096, 0].tolist() for block in range(3)]
    assert rows == [ROWS[6].tolist(), ROWS[0].tolist(), ROWS[1].tolist()]


def test_pointer_offsets_are_divided_by_the_pointer_span(graphs):
    tracker = sam_video.VideoTracker([{"x": 0.5, "y": 0.5}], None, 10)
    for _ in range(3):
        tracker(picture())
    diffs = graphs["pointer_tpos"].feeds[-1]["normalized_diffs"].tolist()
    assert len(diffs) == 16 and diffs[:3] == pytest.approx([2 / 9, 1 / 9, 1 / 9])


def test_the_matte_is_a_probability_in_the_frames_own_size(graphs):
    matte = sam_video.VideoTracker([{"x": 0.5, "y": 0.5}], None, 10)(picture())
    assert matte.shape == (90, 160) and 0.99 < float(matte.min()) <= 1.0


def matte_job(monkeypatch, clip: dict, tracker_ready: bool) -> tuple[list, dict]:
    from app import matte_cache, render_api
    from app.renderer import FrameRenderer

    seen, stored = [], {}
    monkeypatch.setattr(render_api.jobs, "submit", lambda kind, operation: operation("j", lambda fraction: None, lambda: False))
    monkeypatch.setattr(
        FrameRenderer, "media_frame", lambda self, placed, at: seen.append(round(at, 4)) or np.zeros((90, 160, 3), np.uint8)
    )
    monkeypatch.setattr(model_manager, "ready", lambda model: tracker_ready if model == "click-track" else True)
    monkeypatch.setattr(render_api, "matte_store", lambda key, at, alpha: stored.setdefault(round(at, 4), alpha))
    monkeypatch.setattr("app.segmentation.raw_alpha", lambda image, model, points=None, box=None: np.zeros(image.shape[:2], np.float32))
    monkeypatch.setattr(matte_cache, "available", lambda key: [])
    render_api.build_mattes(render_api.MatteInput(clip=clip, fps=10))
    return seen, stored


def test_a_trimmed_clips_mattes_come_from_its_own_part_of_the_file(monkeypatch):
    clip = {"id": "c", "kind": "video", "mediaId": "m", "start": 0, "duration": 0.3, "sourceIn": 2.0, "cutout": {"model": "object-cutout"}}
    _, stored = matte_job(monkeypatch, clip, False)
    assert sorted(stored) == [2.0, 2.1, 2.2, 2.3]


def test_tracking_runs_forward_then_backward_from_the_prompts_frame(monkeypatch):
    fed = []

    class Tracker:
        def __init__(self, points, box, frames):
            fed.append([])

        def __call__(self, image):
            return np.ones(image.shape[:2], np.float32)

    monkeypatch.setattr(sam_video, "VideoTracker", Tracker)
    cutout = {"model": "click-select", "point": {"x": 0.5, "y": 0.5, "t": 0.2}}
    clip = {"id": "c", "kind": "video", "mediaId": "m", "start": 0, "duration": 0.3, "sourceIn": 0.0, "cutout": cutout}
    seen, stored = matte_job(monkeypatch, clip, True)
    assert seen == [0.2, 0.3, 0.2, 0.1, 0.0] and len(fed) == 2
    assert sorted(stored) == [0.0, 0.1, 0.2, 0.3]


def test_without_the_tracker_sam_2_still_runs_frame_by_frame(monkeypatch):
    cutout = {"model": "click-select", "point": {"x": 0.5, "y": 0.5, "t": 0.2}}
    clip = {"id": "c", "kind": "video", "mediaId": "m", "start": 0, "duration": 0.3, "sourceIn": 0.0, "cutout": cutout}
    seen, _ = matte_job(monkeypatch, clip, False)
    assert seen == [0.0, 0.1, 0.2, 0.3]


@pytest.mark.skipif(
    not model_manager.ready("click-track") or not model_manager.ready("click-select"), reason="SAM 2 weights are not downloaded here"
)
def test_a_moving_subject_is_followed_where_a_fixed_point_loses_it():
    from app.segmentation import raw_alpha

    def frame(step: int) -> tuple[np.ndarray, np.ndarray]:
        image = np.full((256, 256, 3), 25, np.uint8)
        rows, columns = np.ogrid[:256, :256]
        disc = (rows - 128) ** 2 + (columns - (60 + 12 * step)) ** 2 < 32**2
        image[disc] = (235, 190, 60)
        image[200:240, 20:60] = (60, 170, 235)
        return image, disc

    def overlap(matte: np.ndarray, disc: np.ndarray) -> float:
        return float(((matte > 0.5) & disc).sum() / max(1, ((matte > 0.5) | disc).sum()))

    seed = [{"x": 60 / 256, "y": 0.5}]
    from app import segmentation

    # Earlier tests leave image sessions cached; the tracker is large, so it
    # starts from released memory and gives its own back before SAM 2 runs.
    segmentation._sessions.clear()
    segmentation._embeddings.clear()
    tracker = sam_video.VideoTracker(seed, None, 5)
    tracked = [overlap(tracker(frame(step)[0]), frame(step)[1]) for step in range(5)]
    del tracker
    sam_video._sessions.clear()
    fixed = overlap(raw_alpha(frame(4)[0], "click-select", seed), frame(4)[1])
    assert min(tracked) > 0.95 and fixed < 0.5
