"""AdjustTrack (P4 of the planar tracking plan): reference points that remove a track's drift, as Mocha's does, and
Auto nudge. A track drifting by a known amount is corrected by points put back on their features at keyed frames."""

from __future__ import annotations

import subprocess

import numpy as np
import pytest
from app import planar_bench
from app.durable import write_json
from app.main import app
from app.planar_api import STORE, adjusted_track
from fastapi.testclient import TestClient

W, H = 640, 360
CORNERS = np.array([[200.0, 100.0], [440.0, 110.0], [430.0, 270.0], [210.0, 260.0]])


def _drifting(frames: int = 41) -> dict:
    """A raw track whose true motion is a slow pan of 1 px a frame, with a drift of 0.25 px a frame rightward and
    0.1 down added on top (what a slipping track looks like)."""
    out = {}
    for i in range(frames):
        true = np.array([[1, 0, 1.0 * i], [0, 1, 0], [0, 0, 1]], float)
        drift = np.array([[1, 0, 0.25 * i], [0, 1, 0.1 * i], [0, 0, 1]], float)
        out[str(i)] = (drift @ true).ravel().tolist()
    return out


def _truth(i: int) -> np.ndarray:
    return CORNERS + [1.0 * i, 0]


def _points(keyed: list[int]) -> list[dict]:
    """The four surface corners as reference points, master frame 0, put back on their features at the keyed frames."""
    return [
        {"master": 0, "home": (c / [W, H]).tolist(), "keys": {str(k): (_truth(k)[n] / [W, H]).tolist() for k in keyed}}
        for n, c in enumerate(CORNERS)
    ]


def _corners(matrix) -> np.ndarray:
    import cv2

    return cv2.perspectiveTransform(CORNERS.reshape(-1, 1, 2), np.array(matrix, float).reshape(3, 3)).reshape(-1, 2)


def test_points_put_back_at_keyed_frames_remove_the_drift_between_them():
    frames = _drifting()
    adjusted = adjusted_track(frames, _points([20, 40]), (W, H))
    raw_error = [float(np.abs(_corners(frames[str(i)]) - _truth(i)).max()) for i in range(41)]
    fixed_error = [float(np.abs(_corners(adjusted[str(i)]) - _truth(i)).max()) for i in range(41)]
    assert raw_error[40] > 9 and max(fixed_error) < 1e-3  # a linear drift: the corrections run linearly, so exact
    assert adjusted["0"] == frames["0"]  # the master frame unchanged


def test_corrections_hold_past_the_last_key_and_fewer_points_still_correct():
    frames = _drifting()
    held = adjusted_track(frames, _points([20]), (W, H))
    assert float(np.abs(_corners(held["20"]) - _truth(20)).max()) < 1e-3
    assert float(np.abs(_corners(held["30"]) - _truth(30)).max()) < float(np.abs(_corners(frames["30"]) - _truth(30)).max())
    one = adjusted_track(frames, _points([40])[:1], (W, H))  # one point: a shift
    assert float(np.abs(_corners(one["40"]) - _truth(40)).max()) < 1e-3
    assert adjusted_track(frames, [], (W, H)) == {k: np.array(v).round(9).tolist() for k, v in frames.items()}


def test_the_adjusted_track_is_what_the_engine_reads_back_and_applies():
    STORE.mkdir(parents=True, exist_ok=True)
    write_json(
        STORE / "drifty.json",
        {"media": "m", "fps": 30.0, "size": [W, H], "reference": 0, "frames": _drifting(), "confidence": {str(i): 1.0 for i in range(41)}},
    )
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    set_ = client.post("/api/planar/adjust/drifty", json={"points": _points([20, 40])}).json()
    assert set_["points"] == 4 and set_["keys"] == 8 and set_["frames"] == 41
    surface = ",".join(f"{v:.6f}" for v in (CORNERS / [W, H]).ravel())
    data = client.get("/api/planar/track/drifty", params={"surface": surface}).json()
    corners = np.array(data["corners"][30]) * [W, H]
    assert float(np.abs(corners - _truth(30)).max()) < 1e-3 and len(data["adjusted"]) == 41 and len(data["adjust"]) == 4
    cleared = client.post("/api/planar/adjust/drifty", json={"points": []}).json()
    assert cleared["frames"] == 0 and "adjusted" not in client.get("/api/planar/track/drifty").json()


def test_auto_nudge_finds_a_points_feature_again(tmp_path):
    """On a benchmark shot tracked exactly (its true homographies as the track), a point a few pixels off its feature
    is found within a fraction of a pixel."""
    import cv2
    from app.media import ingest_path

    s = planar_bench.Scenario(**{**planar_bench.SCENARIOS["moderate"].__dict__, "frames": 12})
    frames, truth, _ = planar_bench.shot(s)
    path = tmp_path / "nudge.mkv"
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
            f"{s.width}x{s.height}",
            "-r",
            "30",
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
    for frame in frames:
        encode.stdin.write(frame.tobytes())
    encode.stdin.close()
    assert encode.wait() == 0
    media_id = ingest_path(path, "nudge.mkv")["id"]
    exact = {
        str(i): cv2.getPerspectiveTransform(truth[0].astype(np.float32), truth[i].astype(np.float32)).ravel().tolist() for i in range(12)
    }
    write_json(
        STORE / "nudged.json",
        {"media": media_id, "fps": 30.0, "size": [s.width, s.height], "reference": 0, "frames": exact, "confidence": {}},
    )
    feature = truth[0].mean(axis=0)  # the plane's centre on frame 0
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    found = client.post(
        "/api/planar/nudge",
        json={
            "media_id": media_id,
            "layer_id": "nudged",
            "master": 0,
            "home": (feature / [s.width, s.height]).tolist(),
            "frame": 10,
            "patch": 31,
            "motion": 12,
        },
    ).json()
    want = cv2.perspectiveTransform(feature.reshape(1, 1, 2), np.array(exact["10"]).reshape(3, 3)).reshape(2)
    got = np.array(found["at"]) * [s.width, s.height]
    assert found["score"] > 0.8 and float(np.linalg.norm(got - want)) < 0.5, (found, want)
    assert (
        client.post(
            "/api/planar/nudge", json={"media_id": media_id, "layer_id": "nudged", "master": 0, "home": [0.001, 0.001], "frame": 10}
        ).status_code
        == 409
    )


@pytest.mark.parametrize("count", [5, 6])
def test_more_than_four_points_fit_by_least_squares(count):
    frames = _drifting()
    pts = _points([40])
    extra = [
        {
            "master": 0,
            "home": ((CORNERS[0] + CORNERS[2]) / 2 / [W, H]).tolist(),
            "keys": {"40": (((_truth(40)[0] + _truth(40)[2]) / 2) / [W, H]).tolist()},
        }
    ]
    adjusted = adjusted_track(frames, pts + extra * (count - 4), (W, H))
    assert float(np.abs(_corners(adjusted["40"]) - _truth(40)).max()) < 1e-3
