"""Clips shaped like a mirrorless camera's 10-bit 4:2:2 recordings decode, frame for frame.

The footage a reviewer brings (4K at 25 and 100 fps, H.264 High 4:2:2 and HEVC Main 4:2:2 10, yuv422p10le) cannot
ship with the tests, so each clip is made here at a small size with the same codec, profile, pixel format and rate.
The H.264 clip is intra only, as an ALL-I recording is; the HEVC clip has a long GOP, as an IPB one does, so reaching
its last frame needs a decode from a keyframe. A bright bar three pixels wide steps three pixels to the right on each
frame, so the column it is found in names the frame: a dropped, repeated or reordered frame shows as the wrong
column. The chroma carries a pattern across and down the picture, so a decode that took the 4:2:2 planes for 4:2:0
would not match ffmpeg's own.

libx264 and libx265 are GPL and are not in the LGPL ffmpeg formcut ships, so a machine whose ffmpeg cannot write
these streams skips with the reason; the CI runners install an ffmpeg that has both. Decoding needs neither: the
H.264 and HEVC decoders are in every build.
"""

from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg to make the clips")

WIDTH, HEIGHT = 384, 216
SECONDS = 1
BAR = 3
# ffprobe names an intra-only x264 stream "High 4:2:2 Intra", and the profile of an HEVC Main 4:2:2 10 stream by its
# family, the range extensions ("Rext"), as it does for a camera's own files; the pixel format says which it is.
ENCODERS = {
    "h264": ("libx264", ["-profile:v", "high422", "-g", "1", "-crf", "12"], "High 4:2:2"),
    "hevc": ("libx265", ["-profile:v", "main422-10", "-x265-params", "keyint=50:min-keyint=50:log-level=error", "-crf", "12"], "Rext"),
}
CLIPS = [(codec, fps) for codec in ENCODERS for fps in (25, 100)]


def _encoders() -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, check=False).stdout


def _make(folder: Path, codec: str, fps: int) -> Path:
    encoder, options, _ = ENCODERS[codec]
    if encoder not in _encoders():
        pytest.skip(f"this ffmpeg has no {encoder} (the LGPL build formcut ships has none); the CI runners' ffmpeg does")
    target = folder / f"{codec}-{fps}.mp4"
    if target.is_file():
        return target
    luma = f"if(between(X,{BAR}*N,{BAR}*N+{BAR - 1}),235,64)"
    picture = f"nullsrc=size={WIDTH}x{HEIGHT}:rate={fps}:duration={SECONDS},format=yuv422p,"
    picture += f"geq=lum='{luma}':cb='128+40*sin(X/9)':cr='128+40*cos(Y/7)',format=yuv422p10le"
    command = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", picture, "-c:v", encoder, *options, "-pix_fmt", "yuv422p10le"]
    command += ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", str(target)]
    made = subprocess.run(command, capture_output=True, text=True, check=False)
    if made.returncode != 0:
        pytest.skip(f"{encoder} here cannot write 10-bit 4:2:2: {made.stderr.strip()[-200:]}")
    return target


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    folder = tmp_path_factory.mktemp("r5-style")
    return lambda codec, fps: _make(folder, codec, fps)


def _ffprobe(path: Path) -> dict:
    if not shutil.which("ffprobe"):
        pytest.skip("needs ffprobe to read the profile back")
    command = ["ffprobe", "-v", "error", "-count_frames", "-show_streams", "-of", "json", str(path)]
    out = subprocess.run(command, capture_output=True, text=True, check=True)
    return next(s for s in json.loads(out.stdout)["streams"] if s["codec_type"] == "video")


def _reference(path: Path) -> np.ndarray:
    """Every frame as ffmpeg's own command line decodes it to BGR."""
    command = ["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(command, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, HEIGHT, WIDTH, 3)


def _frame_number(frame: np.ndarray) -> int:
    """The frame the bar says this is: the brightest column, three columns to a frame."""
    columns = np.asarray(frame, np.float64)[..., :3].mean(axis=(0, 2))
    return int(np.argmax(columns)) // BAR


def _difference(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16)).mean())


def _read_all(path: Path) -> tuple[int, list[np.ndarray]]:
    from app import video_source

    source = video_source._open(path)
    try:
        frames = []
        source.seek(0)
        while len(frames) < source.frame_count + 5:
            ok, frame = source.read()
            if not ok:
                break
            frames.append(np.asarray(frame))
        return source.frame_count, frames
    finally:
        source.release()


def _read_one(path: Path, index: int) -> np.ndarray:
    from app import video_source

    source = video_source._open(path)
    try:
        source.seek(index)
        ok, frame = source.read()
        assert ok, f"frame {index} did not decode: {getattr(source, 'last_error', '')}"
        return np.asarray(frame)
    finally:
        source.release()


@pytest.mark.parametrize(("codec", "fps"), CLIPS)
def test_the_clip_is_what_the_camera_writes(clips, codec, fps):
    stream = _ffprobe(clips(codec, fps))
    assert stream["codec_name"] == codec
    assert stream["profile"].startswith(ENCODERS[codec][2])
    assert stream["pix_fmt"] == "yuv422p10le"
    assert stream["avg_frame_rate"] == f"{fps}/1"
    assert int(stream["nb_read_frames"]) == fps * SECONDS


@pytest.mark.parametrize("ffprobe", [True, False], ids=["ffprobe", "ffmpeg-only"])
@pytest.mark.parametrize(("codec", "fps"), CLIPS)
def test_the_probe_reads_its_size_rate_and_pixel_format(clips, codec, fps, ffprobe, monkeypatch):
    """With ffprobe, and without it as the LGPL bundle runs (ffmpeg's own report)."""
    from app import media, tools

    path = clips(codec, fps)
    if not ffprobe:
        real = tools.have
        monkeypatch.setattr(tools, "have", lambda program: False if program == "ffprobe" else real(program))
    elif not shutil.which("ffprobe"):
        pytest.skip("needs ffprobe")
    info = media._probe(path, "video")
    assert (info["width"], info["height"]) == (WIDTH, HEIGHT)
    assert info["fps"] == fps
    assert math.isclose(info["duration"], SECONDS, abs_tol=0.05)
    stream = next(s for s in tools.probe(path)["streams"] if s["codec_type"] == "video")
    assert stream["codec_name"] == codec
    assert stream["pix_fmt"] == "yuv422p10le"


@pytest.mark.parametrize("decode", ["native", "pipe"])
@pytest.mark.parametrize(("codec", "fps"), CLIPS)
def test_every_frame_decodes_once_in_order(clips, codec, fps, decode, monkeypatch):
    monkeypatch.setenv("FORMCUT_DECODE", decode)
    monkeypatch.setenv("FORMCUT_HWDEC", "off")
    path = clips(codec, fps)
    count, frames = _read_all(path)
    assert count == fps * SECONDS
    assert len(frames) == fps * SECONDS
    assert all(frame.shape == (HEIGHT, WIDTH, 3) for frame in frames)
    assert [_frame_number(frame) for frame in frames] == list(range(fps * SECONDS))
    reference = _reference(path)
    assert len(reference) == fps * SECONDS
    for index in (0, len(frames) - 1):
        assert _difference(frames[index], reference[index]) < 3, index


@pytest.mark.parametrize("decode", ["native", "pipe"])
@pytest.mark.parametrize(("codec", "fps"), CLIPS)
def test_the_first_and_last_frames_decode_when_asked_for_directly(clips, codec, fps, decode, monkeypatch):
    monkeypatch.setenv("FORMCUT_DECODE", decode)
    monkeypatch.setenv("FORMCUT_HWDEC", "off")
    path = clips(codec, fps)
    reference = _reference(path)
    last = len(reference) - 1
    first, final = _read_one(path, 0), _read_one(path, last)
    assert _frame_number(first) == 0
    assert _frame_number(final) == last == fps * SECONDS - 1
    assert _difference(first, reference[0]) < 3
    assert _difference(final, reference[last]) < 3


@pytest.mark.parametrize("codec", list(ENCODERS))
def test_a_100_fps_project_renders_each_source_frame_at_its_own_time(clips, codec, monkeypatch):
    """The renderer at the project's 100 fps lands every frame index on the source frame of the same index."""
    from app import media, proxies
    from app.renderer import FrameRenderer
    from conftest import make_project

    monkeypatch.setenv("FORMCUT_HWDEC", "off")
    monkeypatch.setattr(proxies, "enabled", lambda: False)  # the HEVC clip would queue a proxy build nobody reads
    path = clips(codec, 100)
    media_id = media.ingest_path(path, path.name)["id"]
    clip = {"id": "v", "kind": "video", "label": "v", "mediaId": media_id, "start": 0.0, "duration": 1.0, "sourceIn": 0.0}
    document = make_project(width=WIDTH, height=HEIGHT, fps=100, duration=1.0, clips=[clip])
    renderer = FrameRenderer(document)
    try:
        seen = [_frame_number(renderer.frame(index / 100)) for index in range(100)]
    finally:
        renderer.close()
    assert seen == list(range(100))
