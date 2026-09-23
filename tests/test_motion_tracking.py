"""Motion tracking: a clip pinned to a moving subject follows its position, and,
when asked, its size and angle.

A synthetic clip holds the ground truth: a textured subject over a textured
background that moves across the frame, grows 1.6 times and turns 40 degrees
clockwise in three seconds. The tracker is measured against it, and track_clip
turns the path into the keyframes a title needs to ride along.
"""

import math
import shutil
import subprocess

import numpy as np
import pytest

cv2 = pytest.importorskip("cv2")
from app.project_tracking import ProjectTrackInput, track_clip
from app.track import TrackBody, track_point
from conftest import text_clip

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg writes the clip")
W, H, FPS, N = 640, 360, 30, 90


def _truth(i: int, grow: bool = True) -> tuple[float, float, float, float]:
    f = i / (N - 1)
    return 200 + 220 * f, 180 + 20 * f, (1.0 + 0.6 * f) if grow else 1.0, (40.0 * f) if grow else 0.0


def _clip(tmp_path, grow: bool = True) -> dict:
    from app import media

    rng = np.random.default_rng(7)
    background = (cv2.GaussianBlur((rng.random((H, W, 3)) * 255).astype(np.uint8), (0, 0), 3) * 0.5 + 64).astype(np.uint8)
    patch = cv2.resize((rng.random((24, 24, 3)) * 255).astype(np.uint8), (120, 120), interpolation=cv2.INTER_NEAREST)
    cv2.putText(patch, "fc", (18, 80), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 5)
    frames = bytearray()
    for i in range(N):
        cx, cy, s, angle = _truth(i, grow)
        a = math.radians(angle)
        matrix = np.array([[s * math.cos(a), -s * math.sin(a), 0.0], [s * math.sin(a), s * math.cos(a), 0.0]])
        matrix[:, 2] = [cx, cy] - matrix[:, :2] @ [60, 60]
        frame = background.copy()
        shape = cv2.warpAffine(np.full((120, 120), 255, np.uint8), matrix, (W, H), flags=cv2.INTER_NEAREST)
        frame[shape > 0] = cv2.warpAffine(patch, matrix, (W, H))[shape > 0]
        frames += frame.tobytes()
    path = tmp_path / ("growing.mkv" if grow else "moving.mkv")
    subprocess.run(
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
            str(FPS),
            "-i",
            "-",
            "-c:v",
            "ffv1",
            str(path),
        ],
        input=bytes(frames),
        check=True,
    )
    return media.ingest_path(path, path.name)


def _errors(points, grow=True):
    worst = [0.0, 0.0, 0.0]
    for point in points:
        i = round(point["t"] * FPS)
        cx, cy, s, angle = _truth(i, grow)
        worst[0] = max(worst[0], math.hypot(point["x"] / 100 * W - cx, point["y"] / 100 * H - cy))
        worst[1] = max(worst[1], abs(point.get("scale", 1.0) - s) / s)
        worst[2] = max(worst[2], abs(point.get("rotation", 0.0) - angle))
    return worst


def test_the_subjects_position_size_and_angle_are_followed(tmp_path):
    record = _clip(tmp_path)
    points = track_point(TrackBody(mediaId=record["id"], x=200 / W * 100, y=180 / H * 100, box=0.2, transform=True))["points"]
    assert points[-1]["t"] >= 2.5, "followed to the end"
    position, scale, angle = _errors(points)
    assert position < 2 and scale < 0.02 and angle < 2, (position, scale, angle)


def test_position_alone_is_followed_as_before(tmp_path):
    record = _clip(tmp_path, grow=False)
    points = track_point(TrackBody(mediaId=record["id"], x=200 / W * 100, y=180 / H * 100))["points"]
    assert points[-1]["t"] >= 2.5 and "scale" not in points[-1]
    assert _errors(points, grow=False)[0] < 3


def _pin(record, follow, flip=False, scale=80.0, rotation=10.0):
    from app.render_document import validate_document

    source = {"id": "v", "kind": "video", "label": "v", "mediaId": record["id"], "start": 0, "duration": 3, "transform": {"flipH": flip}}
    title = text_clip(clip_id="title", duration=3, transform={"scale": scale, "rotation": rotation})
    project = validate_document(
        {
            "title": "t",
            "width": W,
            "height": H,
            "fps": FPS,
            "duration": 3,
            "activeTimeline": 0,
            "timelines": [
                {
                    "id": "tl",
                    "name": "m",
                    "tracks": [{"id": "a", "name": "V", "clips": [source]}, {"id": "b", "name": "T", "clips": [title]}],
                }
            ],
        }
    )
    x = (W - 200) / W if flip else 200 / W
    return track_clip(ProjectTrackInput(project=project, target="title", source="v", time=0.0, point=[x, 180 / H], follow=follow))[
        "keyframes"
    ]


def test_a_pinned_title_grows_and_turns_from_its_own_size_and_angle(tmp_path):
    keys = _pin(_clip(tmp_path), ["position", "scale", "rotation"])
    first, last = keys[0]["props"], keys[-1]["props"]
    assert abs(first["scale"] - 80) < 1 and abs(first["rotation"] - 10) < 1, "starts where the title was"
    _cx, _cy, s, angle = _truth(round(keys[-1]["t"] * FPS))
    assert abs(last["scale"] / 80 - s) < 0.03 and abs(last["rotation"] - 10 - angle) < 2
    assert last["posX"] > first["posX"], "and moves with the subject"


def test_a_mirrored_source_turns_the_other_way(tmp_path):
    keys = _pin(_clip(tmp_path), ["position", "rotation"], flip=True)
    assert keys[-1]["props"]["rotation"] < 10 - 20, "turns anticlockwise on the canvas"


def test_position_is_the_default(tmp_path):
    keys = _pin(_clip(tmp_path, grow=False), ["position"])
    assert all(set(key["props"]) == {"posX", "posY"} for key in keys)
