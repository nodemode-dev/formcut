"""Green screens (P8 of the planar tracking plan, on the owner's three phone shots): the screen's corners measured from
its keyed edges, and tracking by them. Checked here on synthetic screens under known homographies, rounded corners
and a notch included, over a busy background, green and blue."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from app.planar_green import green_quad, grown, jitter

W, H = 1280, 720
SCREEN = np.array([[0, 0], [400, 0], [400, 800], [0, 800]], float)  # a phone screen's own corners (where it is placed)
# where its picture's edges are: the screen fills pixels 0 to 399 (pixel centres are whole numbers), so its area runs
# from -0.5 to 399.5: the placing corners less half a pixel on every side (first written as -0.5 to 400.5, which made
# the right and bottom sides look a pixel in)
EDGES = SCREEN - 0.5


PAD = 2  # the screen drawn inside a margin of its source picture, away from the picture's own border


def _screen_picture(colour: tuple[int, int, int]) -> np.ndarray:
    """The screen on its own, 400 x 800 inside a 2 px margin: rounded corners (radius 60) and a notch at the top."""
    flat = np.zeros((800 + 2 * PAD, 400 + 2 * PAD, 3), np.uint8)
    o = PAD
    cv2.rectangle(flat, (o + 60, o), (o + 339, o + 799), colour, -1)
    cv2.rectangle(flat, (o, o + 60), (o + 399, o + 739), colour, -1)
    for cx, cy in ((60, 60), (339, 60), (60, 739), (339, 739)):
        cv2.circle(flat, (o + cx, o + cy), 60, colour, -1, cv2.LINE_AA)
    cv2.rectangle(flat, (o + 130, o), (o + 270, o + 30), (10, 10, 10), -1)  # the notch
    return flat


SUPER = 4  # the screen warped at four times the frame's size and averaged down by area: each pixel's coverage


def _frame(h: np.ndarray, colour=(0, 255, 0)) -> np.ndarray:
    rng = np.random.default_rng(1)
    back = cv2.GaussianBlur((rng.random((H, W, 3)) * 255).astype(np.uint8), (0, 0), 3)  # busy, not the screen's colour
    back[:, :, 1] = (back[:, :, 1] * 0.5).astype(np.uint8)
    back[:, :, 0] = (back[:, :, 0] * 0.5).astype(np.uint8)
    # frame pixel x covers x - 0.5 to x + 0.5; at SUPER times its size its sub-pixel centres are SUPER * x + (SUPER - 1) / 2
    up = np.array([[SUPER, 0, (SUPER - 1) / 2], [0, SUPER, (SUPER - 1) / 2], [0, 0, 1]], float)
    shifted = up @ h @ np.array([[1, 0, -PAD], [0, 1, -PAD], [0, 0, 1]], float)
    size = (W * SUPER, H * SUPER)
    flat = _screen_picture(colour)
    full = np.zeros((800 + 2 * PAD, 400 + 2 * PAD), np.uint8)
    full[PAD : PAD + 800, PAD : PAD + 400] = 255
    down = lambda img: cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)  # noqa: E731
    warped = down(cv2.warpPerspective(flat, shifted, size, flags=cv2.INTER_LINEAR)).astype(np.float32)
    inside = down(cv2.warpPerspective(full, shifted, size, flags=cv2.INTER_LINEAR)).astype(np.float32)[..., None] / 255
    out = back.copy()
    out[cv2.dilate((inside[..., 0] > 0).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0] = (12, 12, 12)  # the bezel
    # the warped screen is already faded at its edge (blended with the black around it): over the background as it is
    return np.clip(np.round(out * (1 - inside) + warped), 0, 255).astype(np.uint8)


def _homography(k: int) -> np.ndarray:
    corners = np.array([[460, 100], [800, 130], [780, 640], [430, 610]], float) + np.array(
        [[3.3 * k, 1.7 * k], [2.1 * k, -1.1 * k], [-1.4 * k, 2.6 * k], [0.7 * k, -0.9 * k]]
    )
    return cv2.getPerspectiveTransform(SCREEN.astype(np.float32), corners.astype(np.float32))


@pytest.mark.parametrize("screen", ["green", "blue"])
def test_a_screens_corners_are_measured_to_a_fraction_of_a_pixel(screen):
    colour = (0, 255, 0) if screen == "green" else (255, 40, 0)  # BGR
    errors = []
    for k in range(0, 12, 3):
        h = _homography(k)
        found = green_quad(_frame(h, colour), screen)
        truth = cv2.perspectiveTransform((EDGES - [0, 0]).reshape(-1, 1, 2), h).reshape(-1, 2)
        assert found is not None
        errors.append(np.linalg.norm(found - truth, axis=1).max())
    assert max(errors) < 0.3, errors  # the rounded corners' sharp corners and the notch's side, under perspective


def test_no_screen_is_found_where_there_is_none_and_the_jitter_of_a_still_one_is_nothing():
    rng = np.random.default_rng(2)
    noise = (rng.random((H, W, 3)) * 80).astype(np.uint8)
    assert green_quad(noise) is None
    still = green_quad(_frame(_homography(0)))
    assert jitter([still] * 9) == pytest.approx(0.0, abs=1e-9)
    assert np.allclose(grown(SCREEN, 0.1).mean(axis=0), SCREEN.mean(axis=0))


def test_tracking_by_the_screen_follows_it_through_the_engine(tmp_path):
    """The engine's track job with settings screen: green, on a video of the synthetic screen moving: every frame's
    surface corners on the truth."""
    import subprocess
    import time

    from app.main import app
    from app.media import ingest_path
    from fastapi.testclient import TestClient

    path = tmp_path / "screen.mkv"
    encode = subprocess.Popen(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{W}x{H}",
            "-r",
            "24",
            "-i",
            "-",
            "-c:v",
            "ffv1",
            "-pix_fmt",
            "bgr0",
            str(path),
        ],
        stdin=subprocess.PIPE,
    )
    for k in range(12):
        picture = _frame(_homography(k))
        if k in (5, 6):
            picture[60:700, 380:880] = (90, 90, 90)  # the screen hidden (a hand over it) on two frames
        encode.stdin.write(picture.tobytes())
    encode.stdin.close()
    assert encode.wait() == 0
    media_id = ingest_path(path, "screen.mkv")["id"]
    truth0 = cv2.perspectiveTransform(EDGES.reshape(-1, 1, 2), _homography(0)).reshape(-1, 2)
    shape = (grown(truth0, 0.08) / [W, H]).round(6).tolist()
    layer = {"id": "phone", "shapes": [{"points": shape}], "reference": 0, "settings": {"perspective": True, "screen": "green"}}
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    job = client.post("/api/planar/track", json={"media_id": media_id, "layer": layer, "start": 0, "stop": 11 / 24}).json()["job_id"]
    for _ in range(600):
        status = client.get(f"/api/jobs/{job}").json()
        if status["status"] not in ("queued", "running"):
            break
        time.sleep(0.02)
    assert status["status"] == "done", status
    surface = ",".join(f"{v:.6f}" for v in (truth0 / [W, H]).ravel())
    corners = np.array(client.get("/api/planar/track/phone", params={"surface": surface}).json()["corners"]) * [W, H]
    for k in range(12):
        truth = cv2.perspectiveTransform(EDGES.reshape(-1, 1, 2), _homography(k)).reshape(-1, 2)
        assert np.linalg.norm(corners[k] - truth, axis=1).max() < (1.5 if k in (5, 6) else 0.6), k  # 5, 6 filled
    confidence = client.get("/api/planar/track/phone").json()["confidence"]
    assert confidence[5] == confidence[6] == 0.5 and confidence[4] == confidence[7] == 1.0
