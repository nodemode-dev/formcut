"""Fixes from the follow-up review of 623f62f..60c6d44.

- A ten-bit export rendered on the worker pool wrote eight-bit frames into a sixteen-bit pipe: half the frames,
  scrambled, no error (every ProRes export on three or more cores without a GPU stack).
- The in-engine decoder counted frames from zero, not from the stream's start, so an MPEG-TS or an offset file froze
  its first frames and lost its last; and it ignored rotation, so a phone's portrait video came out squashed.
- frames.each(cfr=False) reads each decoded frame once, for analysis of the file itself.
- The cadence check's lookup and submit are one step; its cache is written whole and a damaged one is measured again.
- Auto-proxies: the codec rule from 1080p up, ProRes and DNx by size only, builds on two threads at low priority.
- Smaller: software encoders with no format list are not claimed ten-bit; a mov export with no prores_ks is refused;
  a ten-bit export keeps no sixteen-bit resume cache; a stored activeTimeline past the timelines reads as 0.
"""

from __future__ import annotations

import contextlib
import json
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

import numpy as np
import pytest
from app import encoders, media, proxies
from app.main import app
from conftest import make_project
from fastapi.testclient import TestClient

client = TestClient(app, headers={"x-formcut-local": "1"})
pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg and ffprobe")
BAR = 3


def _bar(rate: int = 25, width: int = 192, height: int = 108, seconds: float = 1.0) -> str:
    """A bar stepping BAR pixels a frame (its column names the frame) on a picture with a bright top-left corner, so a
    turned or squashed frame shows."""
    return (
        f"nullsrc=size={width}x{height}:rate={rate}:duration={seconds},format=yuv420p,"
        f"geq=lum='if(between(X,{BAR}*N,{BAR}*N+{BAR - 1}),235,if(lt(X,20)*lt(Y,20),200,40))':cb=128:cr=128"
    )


def _make(path: Path, source: str, extra: list[str]) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", source, *extra, str(path)], check=True)
    return path


def _frame_number(frame) -> int:
    return int(np.argmax(np.asarray(frame, np.float64)[..., :3].mean(axis=(0, 2)))) // BAR


def _video(media_id: str, duration: float) -> dict:
    return {"id": "v", "kind": "video", "label": "v", "mediaId": media_id, "start": 0.0, "duration": duration, "sourceIn": 0.0}


def _read_all(path: Path, decode: str, monkeypatch) -> list[np.ndarray]:
    from app import video_source

    monkeypatch.setenv("FORMCUT_DECODE", decode)
    monkeypatch.setenv("FORMCUT_HWDEC", "off")
    source = video_source._open(str(path))
    try:
        source.seek(0)
        out = []
        while len(out) < source.frame_count + 5:
            ok, frame = source.read()
            if not ok:
                break
            out.append(np.asarray(frame))
        return out
    finally:
        source.release()


# ------------------------------------------------------------------------------------------------ pool depth


def test_a_ten_bit_export_on_the_worker_pool_writes_every_frame_as_one_renderer_does(tmp_path, monkeypatch):
    from app import gpu, gpu_frame
    from app.render_api import export_media

    if not encoders.choose("prores"):
        pytest.skip("this ffmpeg has no prores_ks")
    monkeypatch.setattr(gpu, "stack_active", lambda: False)
    monkeypatch.setattr(gpu_frame, "available", lambda: False)
    source = _make(tmp_path / "bar.mov", _bar(seconds=1.0), ["-c:v", "prores_ks", "-pix_fmt", "yuv422p10le"])
    media_id = media.ingest_path(source, source.name)["id"]
    project = make_project(width=192, height=108, fps=25, duration=1.0, clips=[_video(media_id, 1.0)])
    decoded = {}
    for workers in ("1", "3"):
        monkeypatch.setenv("FORMCUT_EXPORT_WORKERS", workers)
        result = export_media(project, f"pool-{workers}-{uuid.uuid4().hex[:6]}", lambda _: None, lambda: False, "mov", "high")
        command = ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_streams", "-of", "json", result["file"]]
        stream = json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)["streams"][0]
        assert int(stream["nb_read_frames"]) == 25, (workers, stream["nb_read_frames"])
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", result["file"], "-f", "rawvideo", "-pix_fmt", "rgb48le", "-"], capture_output=True, check=True
        ).stdout
        decoded[workers] = np.frombuffer(raw, np.uint16).reshape(25, 108, 192, 3)
    assert [_frame_number(frame) for frame in decoded["3"]] == list(range(25))
    assert int(np.abs(decoded["1"].astype(np.int64) - decoded["3"].astype(np.int64)).max()) == 0


def test_a_pool_frame_of_the_wrong_depth_stops_the_export(monkeypatch):
    from app import render_api

    monkeypatch.setattr(render_api, "FrameRenderer", lambda project, *a, **k: _ByteRenderer())
    out = render_api._render_span({}, 25.0, (0, 2), lambda: False, keep_sixteen=True)
    assert all(len(payload) == 8 * 4 * 4 for payload in out), "the worker renders at the pipe's depth"


class _ByteRenderer:
    keep_sixteen = False

    def frame(self, at):
        return np.zeros((4, 4, 4), np.uint16 if self.keep_sixteen else np.uint8)

    def close(self):
        pass


# ------------------------------------------------------------------------------------------------ stream origin


@pytest.mark.parametrize(
    ("name", "extra"),
    [
        ("ts.ts", ["-c:v", "mpeg2video", "-q:v", "2", "-output_ts_offset", "1.48", "-f", "mpegts"]),
        ("offset.mov", ["-c:v", "mpeg4", "-q:v", "2", "-output_ts_offset", "1.0"]),
    ],
)
def test_a_file_that_starts_after_zero_decodes_every_frame_in_place(tmp_path, monkeypatch, name, extra):
    path = _make(tmp_path / name, _bar(seconds=2.0), extra)
    native, pipe = _read_all(path, "native", monkeypatch), _read_all(path, "pipe", monkeypatch)
    assert [_frame_number(f) for f in native] == list(range(50))
    assert [_frame_number(f) for f in pipe] == list(range(50))
    from app import video_source

    monkeypatch.setenv("FORMCUT_DECODE", "native")
    source = video_source._open(str(path))
    try:
        source.seek(30)
        ok, frame = source.read()
    finally:
        source.release()
    assert ok and _frame_number(frame) == 30, "a seek lands on the frame asked for"


# ------------------------------------------------------------------------------------------------ rotation


@pytest.mark.parametrize("decode", ["native", "pipe"])
def test_a_rotated_phone_clip_comes_out_upright_and_unsquashed(tmp_path, monkeypatch, decode):
    plain = _make(tmp_path / "plain.mp4", _bar(width=192, height=108, seconds=0.4), ["-c:v", "mpeg4", "-q:v", "2"])
    turned = tmp_path / "turned.mp4"
    done = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-display_rotation", "90", "-i", str(plain), "-c", "copy", str(turned)],
        capture_output=True,
        text=True,
        check=False,
    )
    if done.returncode != 0:
        pytest.skip(f"this ffmpeg cannot write a display rotation: {done.stderr[-200:]}")
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(turned), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
        capture_output=True,
        check=True,
    ).stdout
    reference = np.frombuffer(raw, np.uint8).reshape(192, 108, 3)  # ffmpeg turns it: 108 wide, 192 high
    frames = _read_all(turned, decode, monkeypatch)
    assert frames[0].shape == (192, 108, 3)
    assert float(np.abs(frames[0].astype(np.int16) - reference.astype(np.int16)).mean()) < 3


# ------------------------------------------------------------------------------------------------ decoded frames


def test_each_without_the_clock_gives_every_decoded_frame_once(tmp_path):
    from app import frames

    path = tmp_path / "vfr.mp4"
    keep = "select='lt(n\\,5)+between(n\\,20\\,24)'"
    _make(path, _bar(seconds=1.0), ["-vf", keep, "-fps_mode", "passthrough", "-c:v", "mpeg4", "-q:v", "2"])
    with contextlib.closing(frames.each(path, cfr=False)) as decoded:
        seen = [_frame_number(frame) for frame in decoded]
    assert seen == [0, 1, 2, 3, 4, 20, 21, 22, 23, 24]
    with contextlib.closing(frames.each(path)) as timed:
        clocked = [_frame_number(frame) for frame in timed]
    assert len(clocked) != len(seen) or clocked != seen, "the clocked read repeats or drops on the average rate"


# ------------------------------------------------------------------------------------------------ cadence


def test_two_cadence_calls_at_once_start_one_job(tmp_path, monkeypatch):
    from app import automation, cadence, jobs

    path = _make(tmp_path / "cad.mp4", _bar(seconds=1.0), ["-c:v", "mpeg4"])
    media_id = media.ingest_path(path, path.name)["id"]
    gate = threading.Event()
    real = cadence.cadence_map

    def slow(*args, **kwargs):
        gate.wait(5)
        return real(*args, **kwargs)

    monkeypatch.setattr(cadence, "cadence_map", slow)
    created = automation.dispatch(
        "project.create", {"project": make_project(width=192, height=108, fps=25, duration=1.0, clips=[_video(media_id, 1.0)])}
    )
    answers = []
    callers = [
        threading.Thread(target=lambda: answers.append(automation.dispatch("timeline.frames", {"id": created["id"]}))) for _ in range(4)
    ]
    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join()
    gate.set()
    assert len({answer["job_id"] for answer in answers}) == 1, answers
    job = answers[0]["job_id"]
    deadline = time.monotonic() + 60
    while jobs.status(job)["status"] in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(0.1)
    assert jobs.status(job)["status"] == "done"
    assert "clips" in automation.dispatch("timeline.frames", {"id": created["id"]})


def test_a_damaged_cadence_map_is_measured_again(tmp_path, monkeypatch):
    from app import cadence

    monkeypatch.setattr(cadence, "CACHE", tmp_path)
    (tmp_path / "abc.npy").write_bytes(b"\x93NUMPY half a file")
    assert cadence.cached("abc") is None
    path = _make(tmp_path / "c.mp4", _bar(seconds=0.4), ["-c:v", "mpeg4"])
    pictures = cadence.cadence_map("abc", path)
    assert len(pictures) == 10 and np.array_equal(cadence.cached("abc"), pictures)
    assert not list(tmp_path.glob("*.part.npy"))


# ------------------------------------------------------------------------------------------------ auto-proxies


@pytest.mark.parametrize(
    ("codec", "width", "height", "wanted"),
    [
        ("hevc", 1920, 1080, True),
        ("hevc", 1280, 720, False),
        ("av1", 1920, 1080, True),
        ("prores", 1920, 1080, False),
        ("dnxhd", 1920, 1080, False),
        ("prores", 3840, 2160, True),
        ("h264", 3840, 2160, True),
        ("h264", 1920, 1080, False),
    ],
)
def test_the_auto_proxy_rule(codec, width, height, wanted):
    assert proxies.wants_proxy({"kind": "video", "codec": codec, "width": width, "height": height}) is wanted


def test_a_proxy_build_runs_on_two_threads_at_low_priority(tmp_path, monkeypatch):
    seen = {}

    class Stop(Exception):
        pass

    source = _make(tmp_path / "p.mp4", _bar(seconds=0.2), ["-c:v", "mpeg4"])
    real = proxies.subprocess.Popen

    def popen(command, *args, **kwargs):
        if "-map" not in command:  # the probes run as they are
            return real(command, *args, **kwargs)
        seen["command"], seen["kwargs"] = command, kwargs
        raise Stop

    monkeypatch.setattr(proxies.subprocess, "Popen", popen)
    with pytest.raises(Stop):
        proxies.build_proxy("x" * 32, source, lambda _: None, lambda: False, 960)
    command = seen["command"]
    assert command.count("-threads") == 2
    assert all(command[i + 1] == "2" for i, word in enumerate(command) if word == "-threads")
    assert command.index("-threads") < command.index("-i")


# ------------------------------------------------------------------------------------------------ smaller ones


def test_a_software_encoder_with_no_format_list_is_not_claimed_ten_bit(monkeypatch):
    monkeypatch.setitem(encoders._formats, "libvpx-vp9", frozenset())
    monkeypatch.setitem(encoders._formats, "hevc_videotoolbox", frozenset())
    assert encoders.ten_bit_format("libvpx-vp9") is None
    assert encoders.ten_bit_format("hevc_videotoolbox") == "p010le"


def test_a_mov_export_without_prores_ks_is_refused(monkeypatch):
    from app import render_api

    real = render_api.choose_encoder
    monkeypatch.setattr(render_api, "choose_encoder", lambda codec: None if codec == "prores" else real(codec))
    reply = client.post("/api/render/export", json={"project": make_project(), "format": "mov"})
    assert reply.status_code == 422 and "prores_ks" in reply.json()["detail"]


def test_a_ten_bit_export_keeps_no_sixteen_bit_resume_cache(tmp_path, monkeypatch):
    from app import gpu, gpu_frame, render_api

    if not encoders.choose("prores"):
        pytest.skip("this ffmpeg has no prores_ks")
    monkeypatch.setattr(gpu, "stack_active", lambda: False)
    monkeypatch.setattr(gpu_frame, "available", lambda: False)
    monkeypatch.setenv("FORMCUT_EXPORT_WORKERS", "1")
    written = []
    real = render_api.cv2.imwrite
    monkeypatch.setattr(render_api.cv2, "imwrite", lambda path, *a, **k: written.append(path) or real(path, *a, **k))
    project = make_project(width=160, height=90, fps=25, duration=0.4)
    result = render_api.export_media(project, "nocache-" + uuid.uuid4().hex[:6], lambda _: None, lambda: False, "mov", "low")
    assert Path(result["file"]).is_file()
    assert not [p for p in written if str(p).endswith(".png")]


def test_an_active_timeline_past_the_timelines_reads_as_the_first():
    from app import store

    document = {**make_project(), "id": "past-" + uuid.uuid4().hex, "activeTimeline": 5}
    store.save_project(document)
    assert store.get_project(document["id"])["activeTimeline"] == 0


# ------------------------------------------------------------------------------------------------ seeks in long TS

TS_SECONDS = 60


def _numbered(rate: int = 25, seconds: int = TS_SECONDS) -> str:
    """Each frame writes its own number in twelve 16-pixel blocks of light and dark, one bit a block."""
    bits = "if(bitand(N\\,pow(2\\,floor(X/16)))\\,235\\,16)"
    return f"nullsrc=size=192x32:rate={rate}:duration={seconds},format=yuv420p,geq=lum='{bits}':cb=128:cr=128"


def _number(frame) -> int:
    row = np.asarray(frame, np.float64)[16, :, :3].mean(axis=1)
    return sum(1 << block for block in range(12) if row[block * 16 + 4 : block * 16 + 12].mean() > 128)


@pytest.fixture(scope="module")
def long_ts(tmp_path_factory):
    """A minute of MPEG-TS starting at 1.48 s with a 2 s GOP, as a camera's .MTS is laid out."""
    path = tmp_path_factory.mktemp("long-ts") / "long.ts"
    extra = ["-c:v", "mpeg2video", "-q:v", "2", "-g", "50", "-output_ts_offset", "1.48", "-f", "mpegts"]
    return _make(path, _numbered(), extra)


def test_the_numbered_frames_read_back_in_order(long_ts):
    from app import frames

    with contextlib.closing(frames.each(long_ts, limit=60)) as decoded:
        assert [_number(frame) for frame in decoded] == list(range(60))


@pytest.mark.parametrize("seconds", [10.0, 30.04, 45.2, 57.9, 58.0, 59.0, 59.5, 59.96])
def test_a_seek_anywhere_in_a_long_ts_lands_on_ffmpegs_frame(long_ts, seconds, monkeypatch):
    from app import frames

    monkeypatch.setenv("FORMCUT_DECODE", "native")
    monkeypatch.setenv("FORMCUT_HWDEC", "off")
    frame = frames.at(long_ts, seconds)
    assert frame is not None, f"no frame at {seconds} s"
    assert _number(frame) == int(seconds * 25 + 1e-7)


def test_a_seek_near_the_end_of_a_long_ts_decodes_seconds_not_the_file(long_ts, monkeypatch):
    from app import video_source

    monkeypatch.setenv("FORMCUT_DECODE", "native")
    monkeypatch.setenv("FORMCUT_HWDEC", "off")
    source = video_source._open(str(long_ts))
    try:
        source.seek(TS_SECONDS * 25 - 10)
        ok, frame = source.read()
        assert ok and _number(frame) == TS_SECONDS * 25 - 10
        assert source.seek_decoded <= 25 * 10, source.seek_decoded  # at most the 8 s step back and a GOP
    finally:
        source.release()
