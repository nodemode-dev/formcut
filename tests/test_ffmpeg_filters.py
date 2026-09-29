"""An ffmpeg without zscale (v2.2.7). The owner's formcut ran the ffmpeg on their PATH, which has no zscale (it needs
libzimg), and the demo's BT.2020 clip failed: "Error opening output files: Filter not found". formcut now asks ffmpeg
which filters it has: zscale where there, else ffmpeg's own colorspace filter, which every ffmpeg has."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from app import tools, video_source

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo" / "input-clip-example.mp4"


def test_the_filter_list_is_read_from_ffmpeg():
    names = tools.filters()
    assert "scale" in names and "colorspace" in names  # built into every ffmpeg


def _first_frame(monkeypatch, available):
    monkeypatch.setattr(tools, "filters", lambda: frozenset(available))
    source = video_source.VideoSource(str(DEMO))
    try:
        ok, frame = source.read()
        assert ok and frame is not None, getattr(source, "last_error", "")
        return source.tonemap, np.asarray(frame, dtype=np.float32)
    finally:
        source.release()


@pytest.mark.skipif(not DEMO.is_file(), reason="the demo clip is not in this checkout")
def test_a_bt2020_clip_decodes_without_zscale_and_looks_the_same(monkeypatch):
    everything = tools.filters()
    if "zscale" not in everything:
        pytest.skip("this ffmpeg has no zscale to compare with")
    with_zscale, reference = _first_frame(monkeypatch, everything)
    assert with_zscale.startswith("zscale=")
    without, frame = _first_frame(monkeypatch, everything - {"zscale"})
    assert without.startswith("colorspace=iprimaries=bt2020")
    assert frame.shape == reference.shape and float(np.abs(frame - reference).mean()) < 4.0  # the same picture, near enough
    neither, _ = _first_frame(monkeypatch, everything - {"zscale", "colorspace"})
    assert neither == ""  # swscale's rule, rather than a filter ffmpeg does not have


def test_hdr_without_zscale_is_converted_by_matrix_rather_than_failing(monkeypatch):
    monkeypatch.setattr(tools, "filters", lambda: frozenset({"scale", "colorspace", "tonemap"}))
    assert video_source.tonemap_for({"color_transfer": "smpte2084"}).startswith("scale=in_color_matrix=bt2020")
    monkeypatch.setattr(tools, "filters", lambda: frozenset({"scale", "zscale", "tonemap"}))
    assert "tonemap=tonemap=hable" in video_source.tonemap_for({"color_transfer": "smpte2084"})
