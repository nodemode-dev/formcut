"""Real-ESRGAN upscaling in tiles: exact where the model is, seamless where it reads around.

The model itself is a 64 MB download, so these stand in for it: a pixel-wise x4 and
a x4 that reads its neighbours, as a network's receptive field does. Tiling must
reproduce the whole-picture result for both; the second only because each tile is
read with a margin of context.
"""

import numpy as np
from app import ai_upscale, model_manager
from app.main import app
from fastapi.testclient import TestClient
from PIL import Image


def _nearest(batch: np.ndarray) -> np.ndarray:
    return batch.repeat(4, axis=2).repeat(4, axis=3)


def _blurred(batch: np.ndarray) -> np.ndarray:
    padded = np.pad(batch, ((0, 0), (0, 0), (1, 1), (1, 1)), mode="edge")
    height, width = batch.shape[2:]
    box = sum(padded[:, :, dy : dy + height, dx : dx + width] for dy in range(3) for dx in range(3)) / 9.0
    return _nearest(box)


def _picture(height=70, width=90):
    rng = np.random.default_rng(7)
    return rng.integers(0, 256, (height, width, 3), dtype=np.uint8)


def test_tiles_reproduce_a_pixelwise_model_exactly():
    picture = _picture()
    whole = ai_upscale.upscale_rgb(picture, _nearest, tile=1000)
    tiled = ai_upscale.upscale_rgb(picture, _nearest, tile=32, margin=4)
    assert tiled.shape == (280, 360, 3) and np.array_equal(tiled, whole)


def test_the_margin_hides_the_seams_of_a_model_that_reads_around():
    picture = _picture()
    whole = ai_upscale.upscale_rgb(picture, _blurred, tile=1000)
    assert np.array_equal(ai_upscale.upscale_rgb(picture, _blurred, tile=32, margin=4), whole)
    assert not np.array_equal(ai_upscale.upscale_rgb(picture, _blurred, tile=32, margin=0), whole), "without a margin the seams show"


def test_an_image_keeps_its_alpha_and_takes_the_asked_size():
    image = Image.new("RGBA", (40, 30), (200, 100, 50, 128))
    doubled = ai_upscale.upscale_image(image, 2.0, _nearest)
    assert doubled.size == (80, 60) and doubled.mode == "RGBA"
    assert doubled.getpixel((40, 30))[3] == 128


def test_ai_upscaling_waits_for_its_model(monkeypatch):
    monkeypatch.setattr(model_manager, "ready", lambda model: False)
    monkeypatch.setattr("app.upscale._source", lambda media_id: ({"id": media_id, "kind": "image", "width": 10, "height": 10}, None))
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    reply = client.post("/api/media/m1/upscale", json={"method": "ai", "factor": 2})
    assert reply.status_code == 409 and "model" in reply.json()["detail"]


def test_the_model_is_pinned_to_its_published_checksum():
    assert model_manager.MODELS["ai-upscale"]["license"] == "BSD-3-Clause"
    assert model_manager.PINNED["realesrgan-x4plus.onnx"].startswith("4851ec156207")
