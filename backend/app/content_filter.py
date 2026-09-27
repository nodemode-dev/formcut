"""The content filter for the optional Krea 2 model.

The Krea 2 Community License Agreement (section 4.2) requires whoever deploys the model to implement content
filter measures, and names open-source classifiers such as Falconsai/nsfw_image_detection as one. This is that
classifier (Apache-2.0, a ViT-Base), in the ONNX export onnx-community publishes, run on every picture Krea 2
makes while the filter is enabled. A picture it scores as NSFW at or above the threshold is withheld: it is
deleted before it reaches the library.
"""

from __future__ import annotations

import json
import threading

import cv2
import numpy as np

MODEL = "nsfw-filter"
FOLDER = "nsfw-filter"
THRESHOLD = 0.5  # the classifier's own decision boundary: the NSFW class more likely than the normal one

_lock = threading.Lock()
_session = None
_nsfw_index = 1


def installed() -> bool:
    from .model_manager import ready

    return ready(MODEL)


def _load():
    global _session, _nsfw_index
    with _lock:
        if _session is not None:
            return _session
        import onnxruntime as ort

        from .model_manager import model_file

        labels = json.loads(model_file(f"{FOLDER}/config.json").read_text(encoding="utf-8")).get("id2label") or {}
        _nsfw_index = next((int(k) for k, v in labels.items() if str(v).lower() == "nsfw"), 1)
        _session = ort.InferenceSession(str(model_file(f"{FOLDER}/onnx/model.onnx")), providers=["CPUExecutionProvider"])
        return _session


def nsfw_score(rgb: np.ndarray) -> float:
    """The probability the classifier gives the NSFW class for an RGB picture (uint8, H x W x 3 or 4)."""
    session = _load()
    picture = np.ascontiguousarray(rgb[:, :, :3])
    # the classifier's preprocessor: 224 x 224 (bilinear), scaled to 0..1, normalised by mean 0.5 and std 0.5
    x = cv2.resize(picture, (224, 224), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    x = (x - 0.5) / 0.5
    logits = session.run(None, {session.get_inputs()[0].name: x.transpose(2, 0, 1)[None]})[0][0].astype(np.float64)
    probabilities = np.exp(logits - logits.max())
    probabilities /= probabilities.sum()
    return float(probabilities[_nsfw_index])


def check(rgb: np.ndarray) -> dict:
    """The filter's verdict on a picture: its NSFW score and whether it is withheld."""
    score = nsfw_score(rgb)
    return {"nsfw": round(score, 4), "withheld": score >= THRESHOLD, "threshold": THRESHOLD}
