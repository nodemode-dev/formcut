"""Exporting when the preferred encoder is not there.

formcut's own LGPL ffmpeg for Linux and Windows has no H.264 encoder, and an
MP4 export used to stop with "This build has no working video encoder". The
container's own codecs are now tried best first, so MP4 falls back to MPEG-4
Part 2, which every ffmpeg can write.
"""

from __future__ import annotations

import shutil

import pytest
from app import render_api
from app.encoders import CONTAINERS, estimate_size, tier_flags
from conftest import make_project, text_clip

HAVE_FFMPEG = bool(shutil.which("ffmpeg"))


def encoders_here(monkeypatch, **available: str | None) -> None:
    monkeypatch.setattr(render_api, "choose_encoder", available.get)


def export(container: str, codec: str | None = None) -> dict:
    from app.render_document import validate_document

    project = validate_document(make_project(clips=[text_clip(duration=0.5)], duration=0.5))
    return render_api.export_media(project, f"fallback-{container}-{codec}", lambda fraction: None, lambda: False, container, "high", codec)


def test_mp4_takes_mpeg4_last():
    assert CONTAINERS["mp4"][-1] == "mpeg4" and CONTAINERS["mp4"][0] == "h264"


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg writes the file")
def test_an_mp4_without_an_h264_encoder_is_written_with_mpeg4(monkeypatch):
    encoders_here(monkeypatch, mpeg4="mpeg4")
    result = export("mp4")
    assert result["codec"] == "mpeg4" and result["encoder"] == "mpeg4" and result["name"].endswith(".mp4")


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg writes the file")
def test_h264_is_still_chosen_where_it_works(monkeypatch):
    if not shutil.which("ffmpeg") or render_api.choose_encoder.__module__ != "app.encoders":
        pytest.skip("encoder choice is patched elsewhere")
    from app.encoders import choose

    if not choose("h264"):
        pytest.skip("no H.264 encoder on this machine")
    assert export("mp4")["codec"] == "h264"


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg writes the file")
def test_a_requested_codec_that_is_missing_falls_back_within_its_container(monkeypatch):
    encoders_here(monkeypatch, vp9="libvpx-vp9")
    assert export("webm", "av1")["codec"] == "vp9"


def test_nothing_that_can_encode_still_says_so(monkeypatch):
    encoders_here(monkeypatch)
    with pytest.raises(ValueError, match="no working video encoder"):
        export("mp4")


def test_mpeg4_tiers_by_a_fixed_quantiser():
    assert [tier_flags("mpeg4", tier) for tier in ("high", "medium", "low")] == [["-q:v", "2"], ["-q:v", "4"], ["-q:v", "8"]]


def test_an_unknown_tier_is_the_high_one():
    assert tier_flags("mpeg4", "extreme") == ["-q:v", "2"]


def test_the_size_estimate_knows_mpeg4_needs_more_bits_than_h264():
    mpeg4 = estimate_size("mpeg4", 1920, 1080, 30, "high", 60)
    h264 = estimate_size("h264", 1920, 1080, 30, "high", 60)
    assert mpeg4["bytes"] > h264["bytes"]
