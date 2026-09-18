import hashlib
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
        for a, b in zip(points, points[1:]):
            cv2.line(alpha, a, b, color, radius * 2)
    return alpha
