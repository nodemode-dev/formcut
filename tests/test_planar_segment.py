"""Click to spline (P6 of the planar tracking plan): an object outlined by SAM 2.1 as a shape's points. The model is a
download, so here it is stood in for by a matte of a known disc; the outline, the frame read and the refusals are
formcut's own."""

from __future__ import annotations

import subprocess

import numpy as np
from app.main import app
from fastapi.testclient import TestClient
from PIL import Image


def _client():
    return TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})


def _video(tmp_path):
    from app.media import ingest_path

    still = tmp_path / "frame.png"
    Image.new("RGB", (320, 180), (40, 40, 40)).save(still)
    path = tmp_path / "plain.mkv"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(still), "-t", "0.5", "-r", "30", "-c:v", "ffv1", str(path)], check=True
    )
    return ingest_path(path, "plain.mkv")["id"]


def test_a_click_becomes_an_outline_of_the_object(tmp_path, monkeypatch):
    from app import segmentation

    seen = {}

    def disc(image, model, points=None, box=None):
        seen.update(model=model, points=points, shape=image.shape)
        h, w = image.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        return (((xx - 160) ** 2 + (yy - 90) ** 2) < 50**2).astype(np.float32)

    monkeypatch.setattr(segmentation, "cutout_ready", lambda model: True)
    monkeypatch.setattr(segmentation, "raw_alpha", disc)
    media_id = _video(tmp_path)
    out = (
        _client()
        .post("/api/planar/segment", json={"media_id": media_id, "frame": 3, "points": [{"x": 0.5, "y": 0.5}], "detail": 24})
        .json()
    )
    assert seen["model"] == "click-select" and seen["points"][0] == {"x": 0.5, "y": 0.5, "keep": True} and seen["shape"][:2] == (180, 320)
    pts = np.array(out["points"]) * [320, 180]
    radii = np.linalg.norm(pts - [160, 90], axis=1)
    assert 8 <= len(pts) <= 24 and np.abs(radii - 50).max() < 3  # the disc's edge, simplified
    assert 0.1 < out["area"] < 0.15


def test_a_missing_model_and_an_empty_click_are_refused_plainly(tmp_path, monkeypatch):
    from app import segmentation

    media_id = _video(tmp_path)
    monkeypatch.setattr(segmentation, "cutout_ready", lambda model: False)
    refused = _client().post("/api/planar/segment", json={"media_id": media_id, "frame": 0, "points": [{"x": 0.5, "y": 0.5}]})
    assert refused.status_code == 409 and "not downloaded" in refused.json()["detail"]
    monkeypatch.setattr(segmentation, "cutout_ready", lambda model: True)
    monkeypatch.setattr(segmentation, "raw_alpha", lambda image, model, points=None, box=None: np.zeros(image.shape[:2], np.float32))
    empty = _client().post("/api/planar/segment", json={"media_id": media_id, "frame": 0, "points": [{"x": 0.5, "y": 0.5}]})
    assert empty.status_code == 422
