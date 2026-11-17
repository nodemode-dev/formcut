"""Fixes from the Windows run of the released 2.15.8.

- The frozen Windows engine's OpenCV has no videoio, so cv2.VideoCapture is missing and the source monitor answered
  500 for every clip; video frames are read through the timeline's decoder (app/frames.py) everywhere.
- A ten-bit export of a codec that cannot write ten bits here wrote eight silently; it is refused, capabilities say
  per codec what is real, and VP9 and ProRes write real ten bits from the renderer's sixteen-bit frames.
- A project from the RPC had no activeTimeline, so its preview frames failed; every document now has one.
- The cadence check started a new job on every call; a repeated call waits on the running one, which finishes.
- The media record names the video's codec, pixel format and chroma subsampling.
- formcut-engine --help prints its usage instead of starting the server.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pytest
from app import encoders, media
from app.main import app
from conftest import ROOT, make_project
from fastapi.testclient import TestClient

client = TestClient(app, headers={"x-formcut-local": "1"})
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg and ffprobe")


def _make(folder: Path, name: str, source: str, codec: list[str], seconds: float = 1.0) -> Path:
    path = folder / name
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{source}:duration={seconds}", *codec, str(path)], check=True)
    return path


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    path = _make(
        tmp_path_factory.mktemp("win"), "clip.mov", "testsrc2=size=320x180:rate=25", ["-c:v", "prores_ks", "-pix_fmt", "yuv422p10le"]
    )
    media_id = media.ingest_path(path, path.name)["id"]
    return next(media.MEDIA_DIR.glob(f"{media_id}.*")), media_id  # the library's copy (the import takes the file)


@pytest.fixture
def no_videoio(monkeypatch):
    """OpenCV as the frozen Windows engine has it: no VideoCapture."""
    import cv2

    monkeypatch.delattr(cv2, "VideoCapture", raising=False)


def _stream(path) -> dict:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_streams", "-count_frames", "-of", "json", str(path)]
    return json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)["streams"][0]


# ------------------------------------------------------------------------------------------------ no videoio


def test_no_engine_module_reads_video_through_cv2_videocapture():
    found = [
        path.name for path in (ROOT / "backend" / "app").glob("*.py") if re.search(r"cv2\.VideoCapture\(", path.read_text(encoding="utf-8"))
    ]
    assert not found, found


@needs_ffmpeg
def test_the_source_monitor_answers_without_videoio(clip, no_videoio):
    _, media_id = clip
    reply = client.get(f"/api/media/{media_id}/frame?t=0.5&width=160")
    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"] == "image/jpeg"
    import cv2

    picture = cv2.imdecode(np.frombuffer(reply.content, np.uint8), cv2.IMREAD_COLOR)
    assert picture.shape[1] == 160 and picture.std() > 10


@needs_ffmpeg
def test_the_engines_frame_readers_work_without_videoio(clip, no_videoio, tmp_path):
    from app import cadence, frames, planar_green, qc, scenes

    path, _ = clip
    assert frames.size(path) == (320, 180)
    assert frames.count(path) == 25
    assert len(list(frames.each(path))) == 25
    assert frames.at(path, 0.5).shape == (180, 320, 3)
    assert frames.at(tmp_path / "missing.mov", 0.0) is None
    assert len(cadence.changed_shares(path)) == 25
    means, sharp, change = qc._pictures(path)
    assert len(means) == len(sharp) == len(change) == 25
    pictures, quads = planar_green.measure(str(path), frames=5)
    assert len(pictures) == len(quads) == 5
    assert next(iter(scenes._frames(path)), None) is not None


# ------------------------------------------------------------------------------------------------ ten bits


def test_a_ten_bit_format_the_encoder_does_not_list_is_not_claimed(monkeypatch):
    monkeypatch.setitem(encoders._formats, "libvpx-vp9", frozenset({"yuv420p", "yuva420p", "yuv422p", "yuv444p"}))
    assert encoders.ten_bit_format("libvpx-vp9") is None
    assert encoders.pixel_format("libvpx-vp9", True) == "yuv420p"
    monkeypatch.setitem(encoders._formats, "libvpx-vp9", frozenset({"yuv420p", "yuv420p10le"}))
    assert encoders.pixel_format("libvpx-vp9", True) == "yuv420p10le"
    assert encoders.pixel_format("prores_ks", False) in ("yuv422p10le", "yuv420p")


@needs_ffmpeg
def test_capabilities_say_per_codec_what_is_written_at_ten_bits():
    found = client.get("/api/render/status").json()
    assert set(found["tenBit"]) == {"h264", "hevc", "av1", "vp9", "prores"}
    assert found["tenBit"]["h264"] is False
    assert "mov" in found["formats"]
    for codec, claimed in found["tenBit"].items():
        chosen = encoders.choose(codec)
        assert claimed == bool(chosen and encoders.ten_bit_format(chosen)), codec


@needs_ffmpeg
def test_a_ten_bit_h264_export_is_refused_not_written_at_eight_bits(clip):
    _, media_id = clip
    project = make_project(width=320, height=180, fps=25, duration=0.5, clips=[_video(media_id)])
    reply = client.post("/api/render/export", json={"project": project, "format": "mp4", "codec": None, "tenBit": True})
    assert reply.status_code == 422
    assert "Ten-bit h264 is not available here" in reply.json()["detail"]


@needs_ffmpeg
def test_export_media_refuses_too_when_called_directly(clip, monkeypatch):
    from app.render_api import export_media

    _, media_id = clip
    monkeypatch.setitem(encoders._formats, "libvpx-vp9", frozenset({"yuv420p"}))
    project = make_project(width=320, height=180, fps=25, duration=0.2, clips=[_video(media_id, duration=0.2)])
    with pytest.raises(ValueError, match="Ten-bit vp9 is not available here"):
        export_media(project, "refuse-ten", lambda _: None, lambda: False, "webm", "low", "vp9", True)


def _video(media_id: str, duration: float = 0.5, **extra) -> dict:
    return {"id": "v", "kind": "video", "label": "v", "mediaId": media_id, "start": 0.0, "duration": duration, "sourceIn": 0.0, **extra}


def _ramp(folder: Path) -> str:
    """A ten-bit 4:2:2 luma ramp from code 96 to 224 (32 eight-bit steps, 128 ten-bit ones) across 1024 pixels."""
    picture = "nullsrc=size=1024x16:rate=25,format=yuv422p10le,geq=lum='(96+X/8)*4':cb=512:cr=512"
    path = folder / "ramp.mov"
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"{picture}",
        "-t",
        "0.2",
        "-c:v",
        "prores_ks",
        "-pix_fmt",
        "yuv422p10le",
    ]
    subprocess.run([*command, str(path)], check=True)
    return media.ingest_path(path, path.name)["id"]


def _levels(path: str) -> int:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray16le", "-"],
        capture_output=True,
        check=True,
    ).stdout
    row = np.frombuffer(raw, np.uint16).reshape(16, 1024)[8, 16:-16]
    return len(np.unique(row))


@needs_ffmpeg
@pytest.mark.parametrize(("fmt", "codec", "pix"), [("mov", "prores", "yuv422p10le"), ("webm", "vp9", "yuv420p10le")])
def test_a_ten_bit_export_writes_ten_bits_from_the_sixteen_bit_frames(tmp_path, fmt, codec, pix):
    from app.render_api import export_media

    if not encoders.supports_ten_bit(codec):
        pytest.skip(f"this ffmpeg's {encoders.choose(codec)} writes no ten-bit format")
    media_id = _ramp(tmp_path)
    project = make_project(width=1024, height=16, fps=25, duration=0.2, clips=[_video(media_id, duration=0.2)])
    result = export_media(project, f"ten-{codec}", lambda _: None, lambda: False, fmt, "high", codec, True)
    stream = _stream(result["file"])
    assert stream["pix_fmt"] == pix
    assert result["pixelFormat"] == pix
    if codec == "vp9":
        assert stream["profile"] == "Profile 2"
    # an eight-bit pipe would leave the ramp's 32 byte steps; ten bits keep its 128 (less the encoder's loss)
    assert _levels(result["file"]) > 64


# ------------------------------------------------------------------------------------------------ activeTimeline


def test_a_project_from_the_rpc_has_an_active_timeline_and_previews():
    from app import automation, store

    created = automation.dispatch("project.create", {"title": "rpc"})
    assert automation.dispatch("project.get", {"id": created["id"]})["activeTimeline"] == 0
    bare = {k: v for k, v in created.items() if k != "activeTimeline"}
    store.save_project({**bare, "id": "bare-" + created["id"]})
    read = store.get_project("bare-" + created["id"])
    assert read["activeTimeline"] == 0
    session = client.post("/api/render/sessions", json={"project": {k: v for k, v in read.items() if k != "activeTimeline"}, "width": 320})
    assert session.status_code == 201, session.text
    frame = client.get(f"/api/render/sessions/{session.json()['id']}/frame?time=0")
    assert frame.status_code == 200, frame.text


# ------------------------------------------------------------------------------------------------ cadence


@needs_ffmpeg
def test_a_repeated_cadence_call_waits_on_the_running_job_which_finishes(tmp_path):
    from app import automation, jobs

    path = _make(tmp_path, "cad.mp4", "testsrc2=size=160x90:rate=25", ["-c:v", "mpeg4"], seconds=2)
    media_id = media.ingest_path(path, path.name)["id"]
    project = make_project(width=160, height=90, fps=25, duration=2.0, clips=[_video(media_id, duration=2.0)])
    created = automation.dispatch("project.create", {"project": project})
    first = automation.dispatch("timeline.frames", {"id": created["id"]})
    again = automation.dispatch("timeline.frames", {"id": created["id"]})
    if "measuring" in first:
        assert "measuring" not in again or again["job_id"] == first["job_id"]
        deadline = time.monotonic() + 120
        while jobs.status(first["job_id"])["status"] in ("queued", "running") and time.monotonic() < deadline:
            time.sleep(0.2)
        assert jobs.status(first["job_id"])["status"] == "done", jobs.status(first["job_id"])
    done = automation.dispatch("timeline.frames", {"id": created["id"]})
    assert "clips" in done and len(done["clips"]) == 1


# ------------------------------------------------------------------------------------------------ media record


@needs_ffmpeg
def test_the_media_record_names_codec_pixel_format_and_chroma(clip):
    _, media_id = clip
    record = media._find(media_id)
    assert (record["codec"], record["pixFmt"], record["chroma"], record["bitDepth"]) == ("prores", "yuv422p10le", "4:2:2", 10)


@pytest.mark.parametrize(
    ("pix_fmt", "chroma"),
    [
        ("yuv420p", "4:2:0"),
        ("yuv422p10le", "4:2:2"),
        ("yuv444p12le", "4:4:4"),
        ("nv12", "4:2:0"),
        ("p010le", "4:2:0"),
        ("gray", "4:0:0"),
        ("rgb24", "4:4:4"),
        ("weird", ""),
    ],
)
def test_chroma_is_read_from_the_pixel_format(pix_fmt, chroma):
    assert media.chroma_of(pix_fmt) == chroma


# ------------------------------------------------------------------------------------------------ --help


@pytest.mark.parametrize("flag", ["--help", "-h"])
def test_the_engine_prints_its_usage_for_help_and_exits(flag):
    entry = ROOT / "backend" / "desktop_entry.py"
    done = subprocess.run([sys.executable, str(entry), flag], capture_output=True, text=True, timeout=60, cwd=entry.parent, check=False)
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("usage: formcut-engine")
    assert "--selfcheck" in done.stdout and "--mcp" in done.stdout
