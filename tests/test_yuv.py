"""formcut's own conversion of decoded 4:2:0 frames (yuv.py): close to swscale's, the device's pass the CPU's to a
code, the decoder's two modes (planes kept for the device, or converted on its own thread), and the matrix a stream
declares or, undeclared, the one its size implies."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

av = pytest.importorskip("av")

from app import video_source, yuv

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg is needed to make the clips")

CLIPS = {
    "bt709": ("yuv420p", ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]),
    "full601": ("yuvj420p", ["-colorspace", "bt470bg", "-color_range", "pc"]),
    "pq2020": (
        "yuv420p10le",
        ["-colorspace", "bt2020nc", "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-color_range", "tv"],
    ),
}


def _clip(tmp_path, name: str):
    pix, tags = CLIPS[name]
    out = tmp_path / f"{name}.mkv"
    codec = ["-c:v", "ffv1"]  # lossless, any of the three formats, and quick
    subprocess.run(
        [
            FFMPEG,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=96x64:rate=10",
            "-frames:v",
            "2",
            "-pix_fmt",
            pix,
            *codec,
            *tags,
            str(out),
        ],
        check=True,
    )
    return out


def _first(path):
    with av.open(str(path)) as container:
        return next(container.decode(video=0))


@pytest.mark.parametrize("name, matrix, full", [("bt709", "bt709", False), ("full601", "bt470bg", True), ("pq2020", "bt2020nc", False)])
def test_the_conversion_is_swscales_but_for_its_chroma_filter(tmp_path, name, matrix, full):
    frame = _first(_clip(tmp_path, name))
    deep = name == "pq2020"
    planes = yuv.from_av(frame, deep, matrix, full)
    mine = planes.rgba()
    assert mine.shape == (64, 96, 4) and mine.dtype == (np.uint16 if deep else np.uint8)
    assert (mine[..., 3] == (65535 if deep else 255)).all()
    theirs = frame.reformat(format="rgba64le" if deep else "rgb24", interpolation="BICUBIC").to_ndarray()[..., :3].astype(float)
    counts = np.abs(mine[..., :3].astype(float) - theirs) / (257 if deep else 1)
    # the test card is all hard colour edges at 96 x 64, where the two chroma filters part (real footage: about a
    # byte count on average); away from them the conversions agree
    assert np.median(counts) <= 1.0, np.median(counts)


def test_an_undeclared_matrix_follows_the_frame_size(tmp_path):
    frame = _first(_clip(tmp_path, "bt709"))
    assert (yuv.from_av(frame, False, "", False).kr, yuv.from_av(frame, False, "unknown", False).kb) == (0.299, 0.114)
    assert yuv.from_av(frame, False, "bt709", False).kr == 0.2126


def test_the_device_converts_as_the_cpu_does(tmp_path):
    from app import gpu_effects

    if not gpu_effects.active():
        pytest.skip("no device here")
    for name, matrix, full in (("bt709", "bt709", False), ("full601", "bt470bg", True), ("pq2020", "bt2020nc", False)):
        planes = yuv.from_av(_first(_clip(tmp_path, name)), name == "pq2020", matrix, full)
        h, w = planes.shape[:2]
        context = gpu_effects._context(h, w)
        gpu_effects._put(context, context.buffers[0], planes)
        device = np.round(context.download(context.buffers[0], h, w) * planes.grid)
        assert np.abs(device - planes.rgba().astype(float)).max() <= 1, name


def test_the_decoder_keeps_planes_only_when_asked(tmp_path, monkeypatch):
    path = _clip(tmp_path, "bt709")
    source = video_source._open(path)
    if not isinstance(source, video_source.NativeSource):
        pytest.skip("the in-engine decoder is not available here")
    try:
        frame = _first(path)
        assert not source.own_conversion  # the renderer turns it on (yuv.wanted); swscale until then
        assert source._as_bgr(frame).shape == (64, 96, 3)
        source.own_conversion = True
        source.want_planes = True
        kept = source._as_bgr(frame)
        assert isinstance(kept, yuv.PlaneFrame) and kept.shape == (64, 96, 4)
        source.want_planes = False
        converted = source._as_bgr(frame)
        assert isinstance(converted, np.ndarray) and converted.shape == (64, 96, 4)
        assert np.array_equal(converted, kept.rgba())
        source.own_conversion = False
        assert source._as_bgr(frame).shape == (64, 96, 3)  # swscale's BGR, as before
    finally:
        source.release()


def test_a_frame_the_decoder_scales_stays_with_swscale(tmp_path):
    path = _clip(tmp_path, "bt709")
    source = video_source._open(path, limit=48)
    if not isinstance(source, video_source.NativeSource):
        pytest.skip("the in-engine decoder is not available here")
    try:
        source.own_conversion = source.want_planes = True
        assert (source.width, source.height) != (96, 64)
        assert not isinstance(source._as_bgr(_first(path)), yuv.PlaneFrame)
    finally:
        source.release()


def test_formcut_converts_where_the_device_path_runs(monkeypatch):
    monkeypatch.delenv("FORMCUT_YUV", raising=False)
    assert yuv.wanted(True) and not yuv.wanted(False)
    monkeypatch.setenv("FORMCUT_YUV", "0")
    assert not yuv.wanted(True)
    monkeypatch.setenv("FORMCUT_YUV", "1")
    assert yuv.wanted(False)
