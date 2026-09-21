"""SAM 2.1's own video tracker, run with ONNX Runtime.

The seed frame, where the person pointed, is decoded from their prompt and kept
as a conditioning memory. Every later frame is conditioned on a memory bank,
that memory, the six most recent frames' memories and sixteen object pointers,
each with its temporal position, and decoded with no prompt at all, so the
subject is followed rather than found again on each frame. Occlusion is the
model's own: when the subject leaves, its mask is suppressed in the graph, and
it is picked up when it returns.

The graphs are square-zero-labs/sam2.1-tiny-video-onnx (Apache-2.0), exported
from facebook/sam2.1-hiera-tiny. The bank is assembled here as that export's
model card describes: the conditioning memory takes temporal row 6, a memory k
frames back takes row k - 1, the bank is padded to seven blocks and sixteen
pointers by repeating the most recent, and pointer offsets are divided by
min(frames, 16) - 1.
"""

from __future__ import annotations

import json
from collections import deque

import cv2
import numpy as np

from .model_manager import ROOT

MODEL = "click-track"
PREFIX = "sam21-video-"
_sessions: dict = {}


def _session(name: str):
    import onnxruntime as ort

    if name not in _sessions:
        config = ort.SessionOptions()
        config.intra_op_num_threads = 2
        # Memory attention compares 4096 positions with 28736 memory tokens,
        # hundreds of megabytes a layer; without the arena that memory is given
        # back after each run instead of being held for the session's life.
        config.enable_cpu_mem_arena = False
        config.enable_mem_pattern = False
        _sessions[name] = ort.InferenceSession(str(ROOT / f"{PREFIX}{name}.onnx"), sess_options=config, providers=["CPUExecutionProvider"])
    return _sessions[name]


def _constants() -> dict:
    return json.loads((ROOT / f"{PREFIX}constants.json").read_text(encoding="utf-8"))


def _tokens(grid: np.ndarray) -> np.ndarray:
    """[1, C, 64, 64] to the [4096, 1, C] sequence the memory graphs take."""
    return np.ascontiguousarray(grid.reshape(grid.shape[1], -1).T[:, None, :])


class VideoTracker:
    """Follows what a person pointed at on one frame through the frames that come after it.

    Frames are fed in order from the seed; for the frames before the seed, a
    second tracker is fed them in reverse, as SAM 2 tracks backwards.
    """

    def __init__(self, points: list[dict], box: dict | None, frames: int):
        constants = _constants()
        self.size = int(constants["image_size"])
        self.mean = np.array(constants["image_mean"], np.float32)
        self.std = np.array(constants["image_std"], np.float32)
        self.rows = np.array(constants["memory_temporal_positional_encoding"], np.float32)
        self.blocks = int(constants["num_maskmem"])
        self.limit = int(constants["max_object_pointers"])
        self.points, self.box, self.frames = points, box, max(1, frames)
        self.seed: tuple[np.ndarray, np.ndarray] | None = None
        self.seed_pointer: np.ndarray | None = None
        self.recent: deque = deque(maxlen=self.blocks - 1)
        self.pointers: deque = deque(maxlen=self.limit - 1)
        self.steps = 0

    def _encode(self, image: np.ndarray) -> dict:
        big = cv2.resize(image[:, :, :3], (self.size, self.size), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
        values = ((big - self.mean) / self.std).transpose(2, 0, 1)[None]
        session = _session("vision_encoder")
        names = [output.name for output in session.get_outputs()]
        return dict(zip(names, session.run(names, {"pixel_values": values}), strict=True))

    def _decode(self, feats: dict, condition: np.ndarray, coords: list, labels: list) -> dict:
        session = _session("mask_decoder")
        names = [output.name for output in session.get_outputs()]
        feeds = {
            "feats0": feats["feats0"],
            "feats1": feats["feats1"],
            "feats2_cond": condition,
            "input_points": np.array([[coords]], np.float32),
            "input_labels": np.array([[labels]], np.int32),
        }
        return dict(zip(names, session.run(names, feeds), strict=True))

    def _remember(self, feats: dict, decoded: dict, binarize: float) -> tuple[np.ndarray, np.ndarray]:
        feeds = {
            "feats2": feats["feats2"],
            "high_res_mask": decoded["high_res_mask"].astype(np.float32),
            "object_score_logits": decoded["object_score_logits"].reshape(1, 1).astype(np.float32),
            "binarize": np.array(binarize, np.float32),
        }
        tokens, pos = _session("memory_encoder").run(["memory_tokens", "memory_pos"], feeds)
        return tokens, pos

    def _prompt(self) -> tuple[list, list]:
        coords = [[float(p.get("x", 0.5)) * self.size, float(p.get("y", 0.5)) * self.size] for p in self.points[:16]]
        labels = [0 if p.get("keep") is False else 1 for p in self.points[:16]]
        if self.box is not None:
            coords += [
                [float(self.box.get("x0", 0)) * self.size, float(self.box.get("y0", 0)) * self.size],
                [float(self.box.get("x1", 1)) * self.size, float(self.box.get("y1", 1)) * self.size],
            ]
            labels += [2, 3]
        return coords, labels

    def _bank(self) -> tuple[np.ndarray, np.ndarray]:
        if self.seed is None or self.seed_pointer is None:
            raise RuntimeError("the tracker has not been given its seed frame")
        blocks = [(self.seed[0], self.seed[1] + self.rows[self.blocks - 1])]
        for offset, (tokens, pos) in enumerate(reversed(self.recent), start=1):
            blocks.append((tokens, pos + self.rows[offset - 1]))
        newest = blocks[1] if len(blocks) > 1 else blocks[0]
        blocks += [newest] * (self.blocks - len(blocks))
        pointers = [(float(self.steps), self.seed_pointer)]
        pointers += [(float(offset), pointer) for offset, pointer in enumerate(reversed(self.pointers), start=1)]
        latest = pointers[1] if len(pointers) > 1 else pointers[0]
        pointers += [latest] * (self.limit - len(pointers))
        scale = max(1, min(self.frames, self.limit) - 1)
        diffs = np.array([offset / scale for offset, _ in pointers], np.float32)
        places = _session("pointer_tpos").run(["pointer_pos"], {"normalized_diffs": diffs})[0]
        split = np.stack([pointer.reshape(-1) for _, pointer in pointers]).reshape(-1, 64)[:, None, :]
        memory = np.concatenate([tokens for tokens, _ in blocks] + [split]).astype(np.float32)
        memory_pos = np.concatenate([pos for _, pos in blocks] + [np.repeat(places, 4, axis=0)[:, None, :]]).astype(np.float32)
        return memory, memory_pos

    def __call__(self, image: np.ndarray) -> np.ndarray:
        """The matte for the next frame, as a probability in the frame's own size."""
        height, width = image.shape[:2]
        feats = self._encode(image)
        if self.seed is None:
            coords, labels = self._prompt()
            decoded = self._decode(feats, feats["feats2_no_mem"], coords, labels)
            self.seed = self._remember(feats, decoded, 1.0)
            self.seed_pointer = decoded["object_pointer"]
        else:
            self.steps += 1
            memory, memory_pos = self._bank()
            feeds = {
                "current_vision_features": _tokens(feats["feats2"]),
                "current_vision_position_embeddings": _tokens(feats["vision_pos_embed"]),
                "memory": memory,
                "memory_pos": memory_pos,
            }
            condition = _session("memory_attention").run(["conditioned_feats"], feeds)[0]
            decoded = self._decode(feats, condition, [[0.0, 0.0]], [-1])
            self.recent.append(self._remember(feats, decoded, 0.0))
            self.pointers.append(decoded["object_pointer"])
        logits = cv2.resize(decoded["high_res_mask"][0, 0].astype(np.float32), (width, height), interpolation=cv2.INTER_LINEAR)
        return (1 / (1 + np.exp(-np.clip(logits, -30, 30)))).astype(np.float32)
