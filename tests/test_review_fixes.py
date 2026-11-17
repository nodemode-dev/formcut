"""Fixes from the review of feat/review-gaps.

- A cutout computed during an export from a ten-bit source read sixteen-bit pixels as bytes and made (and cached) a
  garbage matte; the models now get bytes, and the matte is the eight-bit decode's.
- A saved project took any number as its rate; it now takes only a project rate.
- An HDR timeline grades and samples its LUT on the sixteen-bit signal, matching apply_float and apply_cube.
- A preview decodes sixteen bits only for a clip with colour work; an export always does.
- The agent tools refuse a rate before creating anything.
- Smaller ones: numpy integers as rates, the proxy settings beside the data folder's other settings, a proxy size
  that is not a whole number, and the layered graph sampling a tetrahedral LUT tetrahedrally.
"""

from __future__ import annotations

import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
from app import media, model_manager, proxies, rates, segmentation
from app.main import app
from conftest import make_project
from fastapi.testclient import TestClient

client = TestClient(app, headers={"x-formcut-local": "1"})
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg to make a clip")
WIDTH, HEIGHT = 320, 180


def _clip(folder: Path, name: str, extra: list[str], codec: list[str]) -> str:
    """A testsrc2 clip, ingested; prores_ks and mpeg4 are in every ffmpeg, the LGPL one included."""
    path = folder / name
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={WIDTH}x{HEIGHT}:rate=24:duration=0.5",
        *extra,
        *codec,
        str(path),
    ]
    subprocess.run(command, check=True)
    return media.ingest_path(path, path.name)["id"]


@pytest.fixture(scope="module")
def ten_bit(tmp_path_factory):
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg")
    return _clip(tmp_path_factory.mktemp("ten-bit"), "ten.mov", [], ["-c:v", "prores_ks", "-pix_fmt", "yuv422p10le"])


def _video(media_id: str, **extra) -> dict:
    return {"id": "v", "kind": "video", "label": "v", "mediaId": media_id, "start": 0.0, "duration": 0.5, "sourceIn": 0.0, **extra}


# ------------------------------------------------------------------------------------------------ cutout on bytes


def test_a_sixteen_bit_picture_reaches_the_models_as_its_bytes():
    deep = np.array([[[0, 257, 65535, 32896]]], np.uint16)
    assert segmentation.as_model_bytes(deep).tolist() == [[[0, 1, 255, 128]]]
    eight = np.array([[[1, 2, 3]]], np.uint8)
    assert segmentation.as_model_bytes(eight) is eight


@needs_ffmpeg
def test_an_export_cutout_from_a_ten_bit_source_is_the_eight_bit_decodes_matte(ten_bit, monkeypatch):
    """With no matte cached, the export computes one; the model saw sixteen-bit values divided by 255 before."""
    from app.renderer import FrameRenderer

    seen, mattes = [], []

    def infer(model, image, options):
        seen.append(image.dtype)
        # a stand-in model that reads bytes the way the real ones do (divided by 255)
        alpha = (image[..., :3].astype(np.float32).mean(axis=2) / 255 > 0.5).astype(np.float32)
        mattes.append(alpha)
        return alpha

    monkeypatch.setattr(segmentation, "cutout_ready", lambda model: True)
    monkeypatch.setattr(segmentation, "_infer", infer)
    segmentation._cache.clear()
    project = make_project(width=WIDTH, height=HEIGHT, fps=24, duration=0.5, clips=[_video(ten_bit, cutout={"model": "object-cutout"})])
    for precise in (False, True):
        renderer = FrameRenderer(project)
        renderer.precise = precise
        try:
            renderer.frame(0.25)
        finally:
            renderer.close()
        segmentation._cache.clear()
    assert len(mattes) == 2, "both renders computed their matte"
    assert seen == [np.uint8, np.uint8]
    agree = float((mattes[0] == mattes[1]).mean())
    assert agree > 0.97, agree  # the two decodes round differently along the threshold
    assert 0.05 < float(mattes[1].mean()) < 0.95, "the matte is a matte, not all one value"


@pytest.mark.skipif(not model_manager.ready("object-cutout"), reason="object-cutout weights are not downloaded here")
@needs_ffmpeg
def test_the_real_model_gives_the_same_matte_from_sixteen_bits_as_from_bytes(ten_bit):
    from app.renderer import FrameRenderer

    clip = _video(ten_bit)
    frames = []
    for precise in (False, True):
        renderer = FrameRenderer(make_project(width=WIDTH, height=HEIGHT, fps=24, duration=0.5, clips=[clip]))
        renderer.precise = precise
        try:
            frames.append(np.asarray(renderer.media_frame(clip, 0.25)))
        finally:
            renderer.close()
    assert frames[0].dtype == np.uint8 and frames[1].dtype == np.uint16
    segmentation._cache.clear()
    eight = segmentation.raw_alpha(frames[0], "object-cutout")
    segmentation._cache.clear()
    sixteen = segmentation.raw_alpha(frames[1], "object-cutout")
    assert float(np.abs(eight - sixteen).mean()) < 0.02


# ------------------------------------------------------------------------------------------------ saved project rate


@pytest.mark.parametrize("fps", [24.5, 1000, 0, "1e999999999", True])
def test_a_saved_project_refuses_a_rate_a_project_cannot_have(fps):
    reply = client.post("/api/projects", json={"title": "bad", "fps": fps, "timelines": []})
    assert reply.status_code == 422, reply.text


@pytest.mark.parametrize("fps", [float("nan"), float("inf")])
def test_the_project_model_refuses_a_rate_that_is_not_finite(fps):
    """Checked on the model: FastAPI cannot write NaN back into its 422 body, whatever the field."""
    from app.projects import ProjectIn
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="Invalid frame rate"):
        ProjectIn(fps=fps)


@pytest.mark.parametrize(("fps", "kept"), [(30, 30), (25, 25), (29.97, 30000 / 1001), ("60000/1001", 60000 / 1001)])
def test_a_saved_project_keeps_a_whole_rate_as_it_was_and_an_ntsc_one_exactly(fps, kept):
    saved = client.post("/api/projects", json={"title": "ok", "fps": fps, "timelines": []}).json()
    assert saved["fps"] == kept and type(saved["fps"]) is type(kept)
    again = client.get(f"/api/projects/{saved['id']}").json()
    assert again["fps"] == kept and type(again["fps"]) is type(kept)


# ------------------------------------------------------------------------------------------------ deep timeline


@needs_ffmpeg
@pytest.mark.parametrize("transfer", ["arib-std-b67", "smpte2084"], ids=["hlg", "pq"])
def test_an_hdr_timeline_grades_and_samples_its_lut_on_the_sixteen_bit_signal(tmp_path, monkeypatch, transfer):
    """Before the colour branch a sixteen-bit frame went through the grade and the LUT as if it were bytes; now the
    grade is apply_float and the LUT apply_cube on the decoded signal, rounded once to sixteen bits."""
    from app import assets, color_grade
    from app.video_source import VideoSource
    from test_colour_depth import _lut, _render

    path = tmp_path / "hdr.mov"
    tags = f"setparams=color_primaries=bt2020:color_trc={transfer}:colorspace=bt2020nc:range=tv"
    picture = "nullsrc=size=256x16:rate=24:duration=0.2,format=yuv422p10le,geq=lum='64+X*3.5':cb=512:cr=512"
    command = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", picture, "-vf", tags, "-c:v", "prores_ks", "-pix_fmt", "yuv422p10le"]
    command += ["-color_primaries", "bt2020", "-color_trc", transfer, "-colorspace", "bt2020nc", str(path)]
    subprocess.run(command, check=True)
    media_id = media.ingest_path(path, path.name)["id"]
    lut = _lut("s-curve")
    grade = {"gain": {"y": 0.3}, "gamma": {"y": 0.4}}
    clip = {"id": "a", "kind": "video", "label": "h", "mediaId": media_id, "start": 0, "duration": 0.1, "sourceIn": 0.0}
    project = make_project(width=256, height=16, fps=24, duration=0.1, clips=[{**clip, "colorGrade": grade, "lutId": lut}])
    project["outputColour"] = "hlg" if transfer == "arib-std-b67" else "pq"
    out = np.asarray(_render(project, monkeypatch, "cpu"))
    assert out.dtype == np.uint16
    source = VideoSource(next(media.MEDIA_DIR.glob(media_id + ".*")), deep=True)
    try:
        source.seek(0)
        ok, decoded = source.read()
    finally:
        source.release()
    assert ok
    signal = np.asarray(decoded)[..., :3].astype(np.float32) / 65535
    graded = np.round(np.clip(color_grade.apply_float(signal, grade), 0, 1) * 65535).astype(np.uint16)
    expected = assets.apply_cube(np.dstack([graded, np.full(graded.shape[:2], 65535, np.uint16)]), assets.load_cube(lut))
    difference = np.abs(out[..., :3].astype(np.int64) - expected[..., :3].astype(np.int64))
    assert float(difference.mean()) < 8 and int(difference.max()) < 64, (difference.mean(), difference.max())


# ------------------------------------------------------------------------------------------------ preview precision


def test_only_a_clip_with_colour_work_wants_sixteen_bits_in_a_preview():
    from app.renderer import wants_precision

    assert not wants_precision({"kind": "video"})
    for extra in ({"colour": {"exposure": 0.2}}, {"colorGrade": {"gain": {"y": 0.1}}}, {"lutId": "x"}, {"inputColour": "s-log3"}):
        assert wants_precision({"kind": "video", **extra}), extra


@needs_ffmpeg
def test_a_preview_reads_an_ungraded_ten_bit_clip_as_bytes_and_an_export_at_sixteen_bits(ten_bit):
    from app.renderer import FrameRenderer

    plain, graded = _video(ten_bit), _video(ten_bit, colorGrade={"gain": {"y": 0.1}})
    kinds = {}
    for name, clip, width in (("preview", plain, WIDTH), ("preview graded", graded, WIDTH), ("export", plain, None)):
        renderer = FrameRenderer(make_project(width=WIDTH, height=HEIGHT, fps=24, duration=0.5, clips=[clip]), width)
        try:
            kinds[name] = np.asarray(renderer.media_frame(clip, 0.25)).dtype
        finally:
            renderer.close()
    assert kinds == {"preview": np.uint8, "preview graded": np.uint16, "export": np.uint16}


# ------------------------------------------------------------------------------------------------ agent tools


@pytest.mark.parametrize("tool", ["create", "set"])
@pytest.mark.parametrize("fps", [24.5, 0.5, 121.0])
def test_the_agent_tools_refuse_a_rate_before_any_call(tool, fps, monkeypatch):
    from app import agent_mcp

    calls = []
    monkeypatch.setattr(agent_mcp, "_rpc", lambda method, params, **kw: calls.append(method) or (True, {"id": "p", "revision": 0}))
    if tool == "create":
        reply = agent_mcp.formcut_create_project(fps=fps)
    else:
        reply = agent_mcp.formcut_set_frame(project_id="p", revision=0, width=1920, height=1080, fps=fps)
    assert reply == agent_mcp.RATE_REFUSED
    assert calls == []


def test_the_agent_tool_sends_the_exact_ntsc_rate(monkeypatch):
    from app import agent_mcp

    sent = []
    monkeypatch.setattr(agent_mcp, "_rpc", lambda method, params, **kw: sent.append(params) or (True, {"id": "p", "revision": 1}))
    agent_mcp.formcut_create_project(fps=29.97)
    assert sent[-1]["commands"][0]["patch"]["fps"] == 30000 / 1001


# ------------------------------------------------------------------------------------------------ smaller ones


def test_numpy_integers_and_floats_are_rates():
    assert rates.exact(np.int64(25)) == Fraction(25)
    assert rates.exact(np.float64(29.97)) == Fraction(30000, 1001)
    with pytest.raises(ValueError):
        rates.exact(np.int64(10**12))


def test_proxy_settings_move_out_of_the_cache_folder(tmp_path, monkeypatch):
    earlier = tmp_path / "proxies" / "settings.json"
    earlier.parent.mkdir()
    earlier.write_text('{"enabled": false, "size": 960}', encoding="utf-8")
    monkeypatch.setattr(proxies, "SETTINGS_PATH", tmp_path / "proxy-settings.json")
    monkeypatch.setattr(proxies, "EARLIER_SETTINGS_PATH", earlier)
    monkeypatch.setattr(proxies, "_settings", None)
    assert proxies.settings() == {"enabled": False, "size": 960, "sizes": [960, 1280, 1920]}
    assert (tmp_path / "proxy-settings.json").is_file() and not earlier.exists()
    assert proxies.SETTINGS_PATH.parent == tmp_path


def test_the_proxy_settings_live_beside_the_data_folders_other_settings():
    from app.paths import DATA_DIR

    assert proxies.SETTINGS_PATH == DATA_DIR / "proxy-settings.json"
    assert proxies.SETTINGS_PATH.parent != proxies.PROXY_DIR


@needs_ffmpeg
@pytest.mark.parametrize("size", [float("inf"), 1280.0, "1280", True])
def test_a_proxy_size_that_is_not_a_whole_number_is_refused(ten_bit, size, monkeypatch):
    from app import automation

    monkeypatch.setattr(proxies, "enqueue", lambda *a, **k: pytest.fail("queued"))
    with pytest.raises(ValueError, match="unknown proxy size"):
        automation.dispatch("media.proxy", {"id": ten_bit, "action": "build", "size": size})


@needs_ffmpeg
@pytest.mark.parametrize("interpolation", ["trilinear", "tetrahedral"])
def test_the_layered_graph_samples_the_baked_lut_as_the_clip_asks(tmp_path, interpolation):
    from app import fast_layers
    from app.render_document import validate_document
    from test_colour_depth import _lut

    media_id = _clip(tmp_path, f"plain-{uuid.uuid4().hex[:6]}.mp4", [], ["-c:v", "mpeg4"])
    clip = _video(media_id, lutId=_lut("s"), lutInterpolation=interpolation)
    project = validate_document(make_project(width=WIDTH, height=HEIGHT, fps=24, duration=0.5, clips=[clip]))
    plan = fast_layers.plan(project, 12)
    assert plan is not None and plan.layers
    text = fast_layers.graph(plan, {0: tmp_path / "grade0.cube"}, WIDTH, HEIGHT)
    assert f":interp={interpolation}" in text
