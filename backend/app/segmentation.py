import hashlib
import itertools
import threading
from collections import OrderedDict

import cv2
import numpy as np

from .model_manager import MODELS, ROOT, ready

_sessions = {}
_cache = OrderedDict()
_embeddings = OrderedDict()
_lock = threading.RLock()
CUTOUT_MODELS = ("object-cutout", "person-cutout", "sharp-cutout", "video-matting", "click-select")
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
SAM_ENCODER = "sam2_hiera_tiny.encoder.onnx"
SAM_DECODER = "sam2_hiera_tiny.decoder.onnx"


def _session(model: str, name: str | None = None):
    """One ONNX Runtime session per model file, made on first use."""
    import onnxruntime as ort

    file = name or next(iter(MODELS[model]["files"]))
    if file not in _sessions:
        config = ort.SessionOptions()
        config.intra_op_num_threads = 2
        _sessions[file] = ort.InferenceSession(str(ROOT / file), sess_options=config, providers=["CPUExecutionProvider"])
    return _sessions[file]


def _stretch(alpha: np.ndarray) -> np.ndarray:
    alpha = alpha.astype(np.float32)
    low, high = float(alpha.min()), float(alpha.max())
    return (alpha - low) / max(1e-6, high - low)


def _u2net(model: str, image: np.ndarray) -> np.ndarray:
    small = cv2.resize(image[:, :, :3], (320, 320), interpolation=cv2.INTER_AREA)
    values = (small.astype(np.float32) / 255 - MEAN) / STD
    session = _session(model)
    output = session.run(None, {session.get_inputs()[0].name: values.transpose(2, 0, 1)[None]})[0]
    return _stretch(np.squeeze(output))


def _isnet(image: np.ndarray) -> np.ndarray:
    """IS-Net at its native 1024 square, normalised the way rembg feeds it."""
    big = cv2.resize(image[:, :, :3], (1024, 1024), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    values = big / max(1.0, float(big.max())) - 0.5
    output = _session("sharp-cutout").run(["output_image"], {"input_image": values.transpose(2, 0, 1)[None]})[0]
    return _stretch(np.squeeze(output))


class VideoMatter:
    """Robust Video Matting through consecutive frames, carrying its recurrent state.

    The four recurrent tensors are what hold the matte steady from one frame to
    the next, so a clip is fed in time order through one matter. Its output is
    already a matte, so it is not stretched.
    """

    def __init__(self):
        self.state = [np.zeros((1, 1, 1, 1), np.float32)] * 4

    def __call__(self, image: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]
        session = _session("video-matting")
        feeds = {f"r{i + 1}i": tensor for i, tensor in enumerate(self.state)}
        feeds["src"] = (image[:, :, :3].astype(np.float32) / 255).transpose(2, 0, 1)[None]
        feeds["downsample_ratio"] = np.array([min(1.0, 512 / max(height, width))], np.float32)
        names = [output.name for output in session.get_outputs()]
        result = dict(zip(names, session.run(names, feeds), strict=True))
        self.state = [result["r1o"], result["r2o"], result["r3o"], result["r4o"]]
        return np.clip(result["pha"][0, 0], 0, 1).astype(np.float32)


def _sam(image: np.ndarray, points: list[dict]) -> np.ndarray:
    """SAM 2: the frame is encoded once and kept, and each set of points is decoded against it.

    A point is {x, y} in 0..1 across the frame, kept unless it says keep: false.
    The returned matte is the decoder's best mask, as a probability.
    """
    height, width = image.shape[:2]
    signature = hashlib.blake2b(cv2.resize(image[:, :, :3], (96, 96), interpolation=cv2.INTER_AREA).tobytes(), digest_size=12).digest()
    features = _embeddings.get(signature)
    if features is None:
        big = cv2.resize(image[:, :, :3], (1024, 1024), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255
        values = ((big - MEAN) / STD).transpose(2, 0, 1)[None]
        names = ["high_res_feats_0", "high_res_feats_1", "image_embed"]
        features = dict(zip(names, _session("click-select", SAM_ENCODER).run(names, {"image": values}), strict=True))
        _embeddings[signature] = features
        while len(_embeddings) > 4:
            _embeddings.popitem(last=False)
    chosen = points[:16]
    coords = [[float(p.get("x", 0.5)) * 1024, float(p.get("y", 0.5)) * 1024] for p in chosen] + [[0.0, 0.0]]
    labels = [0.0 if p.get("keep") is False else 1.0 for p in chosen] + [-1.0]
    feeds = {
        **features,
        "point_coords": np.array([coords], np.float32),
        "point_labels": np.array([labels], np.float32),
        "mask_input": np.zeros((1, 1, 256, 256), np.float32),
        "has_mask_input": np.zeros(1, np.float32),
    }
    masks, scores = _session("click-select", SAM_DECODER).run(["masks", "iou_predictions"], feeds)
    choice = int(np.argmax(scores[0]))
    if len(chosen) == 1:
        # One click is ambiguous between a part and the whole; pointing at what
        # to keep means the whole, so the largest plausible mask is taken.
        areas = (masks[0] > 0).reshape(masks.shape[1], -1).sum(axis=1)
        plausible = [i for i in range(len(scores[0])) if scores[0][i] >= 0.8 * scores[0][choice]]
        choice = max(plausible, key=lambda i: int(areas[i]))
    best = cv2.resize(masks[0, choice].astype(np.float32), (width, height), interpolation=cv2.INTER_LINEAR)
    return (1 / (1 + np.exp(-np.clip(best, -30, 30)))).astype(np.float32)


def _infer(model: str, image: np.ndarray, options: dict) -> np.ndarray:
    if model in ("object-cutout", "person-cutout"):
        return _u2net(model, image)
    if model == "sharp-cutout":
        return _isnet(image)
    if model == "video-matting":
        return VideoMatter()(image)
    points = [p for p in options.get("points") or [] if isinstance(p, dict)]
    if not points:
        raise ValueError("Point at what to keep first")
    return _sam(image, points)


def cutout_alpha(image: np.ndarray, options: dict) -> np.ndarray:
    model = options.get("model", "object-cutout")
    if model not in CUTOUT_MODELS or not ready(model):
        raise ValueError("Download the selected cutout model in Local models first")
    h, w = image.shape[:2]
    small = cv2.resize(image[:, :, :3], (320, 320), interpolation=cv2.INTER_AREA)
    prompt = repr(options.get("points")) if model == "click-select" else ""
    signature = (model, prompt, hashlib.blake2b(small.tobytes(), digest_size=12).digest())
    with _lock:
        alpha = _cache.get(signature)
        if alpha is None:
            alpha = _infer(model, image, options)
            _cache[signature] = alpha
            while len(_cache) > 32:
                _cache.popitem(last=False)
    alpha = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LINEAR)
    threshold = float(options.get("threshold", 0.5))
    feather = max(0.005, float(options.get("feather", 0.1)))
    alpha = np.clip((alpha - threshold + feather / 2) / feather, 0, 1)
    for stroke in options.get("strokes", [])[:2000]:
        points = [(int(p[0] * w), int(p[1] * h)) for p in stroke.get("points", [])[:10000]]
        radius = max(1, int(float(stroke.get("radius", 0.02)) * min(w, h)))
        color = 1 if stroke.get("mode") == "keep" else 0
        for point in points:
            cv2.circle(alpha, point, radius, color, -1)
        for a, b in itertools.pairwise(points):
            cv2.line(alpha, a, b, color, radius * 2)
    return alpha


def feathered(alpha: np.ndarray, options: dict) -> np.ndarray:
    """Apply threshold and feather to a stored matte at read time (BG3).

    These are cheap and interactive, so they are applied when a matte is read
    rather than baked in, which keeps one cached matte usable while the user
    drags the feather slider.
    """
    threshold = float(options.get("threshold", 0.5))
    feather = max(0.005, float(options.get("feather", 0.1)))
    shaped = np.clip((alpha - threshold + feather / 2) / feather, 0, 1)
    # Brush strokes are painted after the model's own guess, so a person can
    # always overrule it. They were being read at read time and then ignored,
    # which made the brush look like it did nothing.
    strokes = options.get("strokes") or []
    if strokes:
        height, width = shaped.shape[:2]
        for stroke in strokes:
            points = [(int(px * width), int(py * height)) for px, py in stroke.get("points", [])]
            if not points:
                continue
            radius = max(1, int(float(stroke.get("radius", 0.02)) * max(width, height)))
            layer = np.zeros((height, width), np.uint8)
            if len(points) == 1:
                cv2.circle(layer, points[0], radius, 255, -1)
            else:
                cv2.polylines(layer, [np.array(points, np.int32)], False, 255, radius * 2)
            soft = cv2.GaussianBlur(layer.astype(np.float32) / 255, (0, 0), max(1, radius * 0.25))
            shaped = np.clip(shaped - soft, 0, 1) if stroke.get("mode") == "erase" else np.clip(shaped + soft, 0, 1)
    return shaped


def raw_alpha(image: np.ndarray, model: str, points: list[dict] | None = None) -> np.ndarray:
    """One model run returning an unshaped 0..1 matte, for the BG3 job.

    Shaping is (a - threshold + feather / 2) / feather, so the identity is a
    threshold of 0.5 with a feather of 1. A threshold of 0 raised every matte
    by a half, and the threshold applied at read time then acted at 0.05.
    """
    return cutout_alpha(image, {"model": model, "threshold": 0.5, "feather": 1.0, "strokes": [], "points": points or []})


def outline(alpha: np.ndarray, max_points: int = 48) -> list[dict]:
    """Trace a matte's largest region into mask anchors.

    Returning a path rather than a matte is deliberate: a person can then move a
    point, add one, or delete one, instead of accepting or rejecting whatever
    the model decided. The outline is simplified so it arrives as something
    editable rather than as several thousand pixels of coastline.
    """
    mask = (alpha > 0.5).astype(np.uint8) * 255
    found, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not found:
        return []
    biggest = max(found, key=cv2.contourArea)
    if cv2.contourArea(biggest) < 16:
        return []
    height, width = alpha.shape[:2]
    # Tighten the tolerance until the outline is small enough to work with.
    tolerance = 0.002 * cv2.arcLength(biggest, True)
    points = biggest
    for _ in range(12):
        points = cv2.approxPolyDP(biggest, tolerance, True)
        if len(points) <= max_points:
            break
        tolerance *= 1.5
    return [{"x": round(float(p[0][0]) / width, 5), "y": round(float(p[0][1]) / height, 5)} for p in points]


def pick_region(alpha: np.ndarray, x: float, y: float, grow: float = 0.0) -> np.ndarray:
    """Keep only the part of a matte the person pointed at.

    A cutout model answers "what is foreground", not "which of these". When a
    frame holds two people, or a person and a chair, the matte contains both and
    there has been no way to say which one was meant. Pointing at one and
    keeping the piece it belongs to is that way, and it needs no extra model:
    the regions are already separate in the matte.
    """
    height, width = alpha.shape[:2]
    solid = (alpha > 0.5).astype(np.uint8)
    count, labels = cv2.connectedComponents(solid)
    if count <= 1:
        return alpha
    column = round(max(0.0, min(1.0, x)) * (width - 1))
    row = round(max(0.0, min(1.0, y)) * (height - 1))
    chosen = int(labels[row, column])
    if chosen == 0:
        # Pointed at background. Take the nearest region rather than returning
        # nothing, because an empty result looks exactly like a broken tool.
        marks = np.argwhere(solid > 0)
        if not len(marks):
            return alpha
        nearest = marks[np.argmin(((marks - (row, column)) ** 2).sum(axis=1))]
        chosen = int(labels[nearest[0], nearest[1]])
    kept = (labels == chosen).astype(np.float32)
    if grow > 0:
        size = max(3, int(grow * min(height, width)) | 1)
        kept = cv2.dilate(kept, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)))
    return (alpha * kept).astype(np.float32)


def region_count(alpha: np.ndarray) -> int:
    """How many separate things the matte found, so the interface can say so."""
    solid = (alpha > 0.5).astype(np.uint8)
    count, labels = cv2.connectedComponents(solid)
    keep = 0
    for index in range(1, count):
        if int((labels == index).sum()) > solid.size * 0.002:
            keep += 1
    return keep
