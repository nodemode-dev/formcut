import hashlib
import itertools
import threading
from collections import OrderedDict

import cv2
import numpy as np

from .model_manager import MODELS, ROOT, ready

_sessions = {}
_cache = OrderedDict()
_lock = threading.RLock()


def cutout_alpha(image: np.ndarray, options: dict) -> np.ndarray:
    model = options.get("model", "object-cutout")
    if model not in ("object-cutout", "person-cutout") or not ready(model):
        raise ValueError("Download the selected cutout model in Local models first")
    h, w = image.shape[:2]
    small = cv2.resize(image[:, :, :3], (320, 320), interpolation=cv2.INTER_AREA)
    signature = (model, hashlib.blake2b(small.tobytes(), digest_size=12).digest())
    with _lock:
        alpha = _cache.get(signature)
        if alpha is None:
            import onnxruntime as ort

            if model not in _sessions:
                path = ROOT / next(iter(MODELS[model]["files"]))
                config = ort.SessionOptions()
                config.intra_op_num_threads = 2
                _sessions[model] = ort.InferenceSession(str(path), sess_options=config, providers=["CPUExecutionProvider"])
            session = _sessions[model]
            values = small.astype(np.float32) / 255
            values = (values - np.array([0.485, 0.456, 0.406], np.float32)) / np.array([0.229, 0.224, 0.225], np.float32)
            output = session.run(None, {session.get_inputs()[0].name: values.transpose(2, 0, 1)[None]})[0]
            alpha = np.squeeze(output).astype(np.float32)
            low, high = float(alpha.min()), float(alpha.max())
            alpha = (alpha - low) / max(1e-6, high - low)
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


def raw_alpha(image: np.ndarray, model: str) -> np.ndarray:
    """One model run returning an unshaped 0..1 matte, for the BG3 job."""
    return cutout_alpha(image, {"model": model, "threshold": 0.0, "feather": 1.0, "strokes": []})


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
    column = int(round(max(0.0, min(1.0, x)) * (width - 1)))
    row = int(round(max(0.0, min(1.0, y)) * (height - 1)))
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
