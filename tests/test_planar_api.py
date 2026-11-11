"""The planar tracker through the engine (P1): a layer tracked over a video in the media library as a job, forwards,
backwards and resumed, its track kept per layer and read back as corners. The video is a benchmark shot encoded
losslessly, so its true corners are known."""

from __future__ import annotations

import os
import shutil
import subprocess
import time

import numpy as np
import pytest
from app import planar_bench
from app.main import app
from conftest import lgpl_ffmpeg
from fastapi.testclient import TestClient


@pytest.fixture
def shot(tmp_path):
    """A benchmark shot as an FFV1 file in the library: (media id, true corners per frame, size, fps)."""
    from app.media import ingest_path

    s = planar_bench.Scenario(**{**planar_bench.SCENARIOS["moderate"].__dict__, "frames": 40})
    frames, truth, _ = planar_bench.shot(s)
    path = tmp_path / "plane.mkv"
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
    item = ingest_path(path, "plane.mkv")
    return item["id"], truth, (s.width, s.height), 30.0


def _client():
    return TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})


def _finish(client, job_id):
    for _ in range(1500):
        status = client.get(f"/api/jobs/{job_id}").json()
        if status["status"] not in ("queued", "running"):
            return status
        time.sleep(0.02)
    return status


def _layer(truth, size, frame=0, scale=0.92, layer_id="screen"):
    c = truth[frame]
    centre = c.mean(0)
    points = ((c - centre) * scale + centre) / size
    return {"id": layer_id, "shapes": [{"points": points.round(6).tolist()}], "reference": frame / 30.0, "settings": {"perspective": True}}


def _errors(client, layer_id, truth, size, frame=0):
    surface = ",".join(f"{v:.6f}" for v in (truth[frame] / size).ravel())
    data = client.get(f"/api/planar/track/{layer_id}", params={"surface": surface}).json()
    corners = np.array(data["corners"]) * size
    return {i: float(np.linalg.norm(corners[k] - truth[i], axis=1).mean()) for k, i in enumerate(data["frames"])}, data


def test_a_layer_is_tracked_over_a_video_as_a_job_and_read_back_as_corners(shot):
    media_id, truth, size, fps = shot
    client = _client()
    job = client.post("/api/planar/track", json={"media_id": media_id, "layer": _layer(truth, size), "start": 0, "stop": 39 / fps}).json()
    done = _finish(client, job["job_id"])
    assert done["status"] == "done" and done["result"]["tracked"] == 39, done
    errors, data = _errors(client, "screen", truth, size)
    assert data["frames"] == list(range(40)) and len(data["confidence"]) == 40
    assert max(errors.values()) < 0.4 and np.mean(list(errors.values())) < 0.2, errors  # P0's accuracy through the API


def test_a_track_resumes_from_where_it_stopped_and_runs_backwards_from_its_reference(shot):
    media_id, truth, size, fps = shot
    client = _client()
    first = _finish(
        client,
        client.post("/api/planar/track", json={"media_id": media_id, "layer": _layer(truth, size), "start": 0, "stop": 20 / fps}).json()[
            "job_id"
        ],
    )
    assert first["result"]["to"] == 20
    refused = client.post(
        "/api/planar/track", json={"media_id": media_id, "layer": _layer(truth, size), "start": 30 / fps, "stop": 39 / fps}
    )
    assert refused.status_code == 409  # frame 30 has no track yet
    again = _finish(
        client,
        client.post(
            "/api/planar/track", json={"media_id": media_id, "layer": _layer(truth, size), "start": 20 / fps, "stop": 39 / fps}
        ).json()["job_id"],
    )
    assert again["status"] == "done", again
    errors, data = _errors(client, "screen", truth, size)
    assert data["frames"] == list(range(40)) and max(errors.values()) < 0.4, errors
    # a layer drawn on the last frame, tracked backwards to the first
    back = _layer(truth, size, frame=39, layer_id="screen-back")
    done = _finish(
        client, client.post("/api/planar/track", json={"media_id": media_id, "layer": back, "start": 39 / fps, "stop": 0}).json()["job_id"]
    )
    assert done["status"] == "done" and done["result"]["to"] == 0, done
    errors, _ = _errors(client, "screen-back", truth, size, frame=39)
    assert max(errors.values()) < 0.4, errors


def test_a_changed_layer_starts_afresh_and_a_range_can_be_cleared(shot):
    media_id, truth, size, fps = shot
    client = _client()
    _finish(
        client,
        client.post("/api/planar/track", json={"media_id": media_id, "layer": _layer(truth, size), "start": 0, "stop": 10 / fps}).json()[
            "job_id"
        ],
    )
    assert len(client.get("/api/planar/track/screen").json()["frames"]) == 11
    assert client.delete("/api/planar/track/screen", params={"start": 6, "stop": 10}).json()["cleared"] == 5
    assert client.get("/api/planar/track/screen").json()["frames"] == list(range(6))
    tighter = _layer(truth, size, scale=0.8)  # a new shape: the old track no longer holds
    _finish(
        client,
        client.post("/api/planar/track", json={"media_id": media_id, "layer": tighter, "start": 0, "stop": 3 / fps}).json()["job_id"],
    )
    assert client.get("/api/planar/track/screen").json()["frames"] == [0, 1, 2, 3]


def test_a_layer_in_front_excludes_what_it_covers(shot):
    media_id, truth, size, fps = shot
    client = _client()
    # a still layer over the plane's left third, drawn where it stays (untracked)
    c = truth[0] / size
    left = c[:, 0].min()
    cover = {
        "id": "hand",
        "shapes": [{"points": [[left - 0.02, 0.0], [left + 0.12, 0.0], [left + 0.12, 1.0], [left - 0.02, 1.0]]}],
        "reference": 0,
        "settings": {},
    }
    job = client.post(
        "/api/planar/track", json={"media_id": media_id, "layer": _layer(truth, size), "start": 0, "stop": 39 / fps, "above": [cover]}
    ).json()
    done = _finish(client, job["job_id"])
    assert done["status"] == "done", done
    errors, _ = _errors(client, "screen", truth, size)
    assert max(errors.values()) < 0.5, errors


def test_bad_requests_are_named(shot):
    media_id, truth, size, _fps = shot
    client = _client()
    layer = _layer(truth, size)
    assert (
        client.post(
            "/api/planar/track", json={"media_id": media_id, "layer": {**layer, "settings": {"warp": 1}}, "start": 0, "stop": 1}
        ).status_code
        == 400
    )
    assert (
        client.post("/api/planar/track", json={"media_id": media_id, "layer": {**layer, "id": "../x"}, "start": 0, "stop": 1}).status_code
        == 400
    )
    assert client.post("/api/planar/track", json={"media_id": "0" * 32, "layer": layer, "start": 0, "stop": 1}).status_code == 404
    assert client.get("/api/planar/track/nothing-here").status_code == 404


def test_a_plane_that_vanishes_ends_the_track_there_not_in_an_error(tmp_path):
    """2.3.6: in the workspace's first run a lost plane stopped the job with "Singular matrix". Now a step that cannot
    be made gives no confidence, and twelve such frames end the track where the plane went, the frames before kept."""
    from app.media import ingest_path

    s = planar_bench.Scenario(**{**planar_bench.SCENARIOS["moderate"].__dict__, "frames": 12})
    frames, truth, _ = planar_bench.shot(s)
    rng = np.random.default_rng(5)
    frames += [(rng.random((s.height, s.width, 3)) * 255).astype(np.uint8) for _ in range(24)]  # the plane gone
    path = tmp_path / "gone.mkv"
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
    media_id = ingest_path(path, "gone.mkv")["id"]
    client = _client()
    done = _finish(
        client,
        client.post(
            "/api/planar/track",
            json={"media_id": media_id, "layer": _layer(truth, (s.width, s.height), layer_id="gone"), "start": 0, "stop": 35 / 30},
        ).json()["job_id"],
    )
    assert done["status"] == "done", done
    assert 11 <= done["result"]["lost"] <= 14, done["result"]
    kept = client.get("/api/planar/track/gone").json()["frames"]
    assert kept[0] == 0 and max(kept) < done["result"]["lost"]


def test_a_step_on_noise_has_no_confidence_and_raises_nothing():
    from app.planar import PlanarTracker, Settings

    rng = np.random.default_rng(3)
    first = (rng.random((180, 320, 3)) * 255).astype(np.uint8)
    matte = np.zeros((180, 320), np.uint8)
    matte[40:140, 80:240] = 255
    tracker = PlanarTracker(first, matte, Settings(perspective=True))
    for _ in range(5):
        h, confidence = tracker.step((rng.random((180, 320, 3)) * 255).astype(np.uint8))
        assert np.all(np.isfinite(h)) and confidence < 0.3


def test_a_track_applied_as_a_corner_pin_and_as_transform_keys(shot):
    """P3: the layer's surface carried to the canvas through the tracked clip's own placement lands on the plane's
    true corners; as Transform, the target's position follows the surface's centre."""
    media_id, truth, size, fps = shot
    client = _client()
    layer = _layer(truth, size)
    _finish(
        client, client.post("/api/planar/track", json={"media_id": media_id, "layer": layer, "start": 0, "stop": 39 / fps}).json()["job_id"]
    )
    surface = (truth[0] / size).round(6).tolist()
    tracked = {
        "id": "plate",
        "kind": "video",
        "label": "plate",
        "start": 0,
        "duration": 40 / fps,
        "mediaId": media_id,
        "planar": {"version": 1, "layers": [{**layer, "surface": surface}]},
    }
    target = {"id": "insert", "kind": "image", "label": "insert", "start": 0, "duration": 40 / fps}
    project = {
        "width": size[0],
        "height": size[1],
        "fps": 30,
        "activeTimeline": 0,
        "timelines": [{"tracks": [{"clips": [target]}, {"clips": [tracked]}]}],
    }
    pin = client.post(
        "/api/planar/apply",
        json={"project": project, "tracked_clip": "plate", "layer_id": "screen", "target_clip": "insert", "kind": "corner-pin"},
    ).json()
    assert pin["frames"] == 40
    points = np.array(pin["cornerPin"]["points"]).reshape(-1, 4, 2) * size
    errors = [float(np.linalg.norm(points[k] - truth[k], axis=1).mean()) for k in range(40)]
    assert max(errors) < 0.5, errors  # the project is the media's size and the plate fills it: corners on the truth
    keys = client.post(
        "/api/planar/apply",
        json={"project": project, "tracked_clip": "plate", "layer_id": "screen", "target_clip": "insert", "kind": "transform"},
    ).json()["keyframes"]
    assert (
        len(keys) == 40
        and keys[0]["props"]["scale"] == pytest.approx(100, abs=0.5)
        and keys[0]["props"]["rotation"] == pytest.approx(0, abs=0.1)
    )
    centre = truth[20].mean(axis=0)
    assert keys[20]["props"]["posX"] == pytest.approx((centre[0] / size[0] - 0.5) * 100, abs=0.2)
    assert keys[20]["props"]["posY"] == pytest.approx((centre[1] / size[1] - 0.5) * 100, abs=0.2)
    refused = client.post(
        "/api/planar/apply", json={"project": project, "tracked_clip": "plate", "layer_id": "nothing", "target_clip": "insert"}
    )
    assert refused.status_code == 400


def _removal(client, media_id, truth, size, fps):
    tracked = _finish(
        client,
        client.post("/api/planar/track", json={"media_id": media_id, "layer": _layer(truth, size), "start": 0, "stop": 6 / fps}).json()[
            "job_id"
        ],
    )
    assert tracked["status"] == "done", tracked
    centre = truth[0].mean(0) / size
    blot = {
        "id": "blot",
        "shapes": [{"points": (centre + np.array([[-0.03, -0.03], [0.03, -0.03], [0.03, 0.03], [-0.03, 0.03]])).round(6).tolist()}],
        "reference": 0,
        "settings": {},
    }
    job = client.post(
        "/api/planar/remove", json={"media_id": media_id, "background": "screen", "remove": blot, "start": 0, "stop": 6 / fps, "reach": 3}
    ).json()
    return _finish(client, job["job_id"])


@pytest.mark.skipif(os.name == "nt", reason="the stand-in ffmpeg is a shell script")
def test_object_removal_writes_its_clip_with_an_ffmpeg_that_has_no_libx264(shot, tmp_path, monkeypatch):
    media_id, truth, size, fps = shot
    lgpl_ffmpeg(tmp_path, monkeypatch)
    done = _removal(_client(), media_id, truth, size, fps)
    assert done["status"] == "done", done
    from app.media import media_path

    out = media_path(done["result"]["media_id"])
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt", "-of", "csv=p=0", str(out)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert probe == "ffv1,yuv444p", probe
    assert done["result"]["frames"] == 7


@pytest.mark.skipif(os.name == "nt", reason="the stand-in ffmpeg is a shell script")
def test_object_removal_reports_an_ffmpeg_that_fails(shot, tmp_path, monkeypatch):
    media_id, truth, size, fps = shot
    real = shutil.which("ffmpeg")
    fails = f'case " $* " in *" -i - "*) cat > /dev/null; echo "disk full" >&2; exit 1;; esac\nexec "{real}" "$@"\n'
    lgpl_ffmpeg(tmp_path, monkeypatch, tail=fails)
    done = _removal(_client(), media_id, truth, size, fps)
    assert done["status"] == "error", done
    assert "Could not write the clip with the object removed" in done["error"] and "disk full" in done["error"], done
