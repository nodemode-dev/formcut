"""H.264 and HEVC through Media Foundation and VA-API: listed, tuned, tested as used, and wired into exports."""

import subprocess

import pytest
from app import encoders


def test_media_foundation_and_vaapi_follow_the_gpu_makers_and_precede_the_installed_encoders():
    for codec, software in (("h264", "libx264"), ("hevc", "libx265")):
        order = encoders.CANDIDATES[codec]
        for family in ("vaapi", "mf"):
            name = f"{codec}_{family}"
            assert name in order and order.index(f"{codec}_amf") < order.index(name) < order.index(software), name


@pytest.mark.parametrize(
    ("encoder", "flag"),
    [
        ("h264_amf", "-qp_i"),
        ("hevc_amf", "-qp_i"),
        ("h264_vaapi", "-qp"),
        ("hevc_vaapi", "-qp"),
        ("h264_mf", "-quality"),
        ("hevc_mf", "-quality"),
    ],
)
def test_each_family_gets_its_own_rate_control_at_every_tier(encoder, flag):
    tiers = [encoders.tier_flags(encoder, quality) for quality in ("high", "medium", "low")]
    assert all(flag in tier for tier in tiers) and len({tuple(tier) for tier in tiers}) == 3
    assert all("-q:v" not in tier for tier in tiers)


def test_only_vaapi_needs_a_device_and_an_upload():
    assert encoders.hardware_io("h264_vaapi") == (["-vaapi_device", "/dev/dri/renderD128"], "format=nv12,hwupload")
    for encoder in ("h264_mf", "h264_nvenc", "h264_amf", "libx264", "mpeg4"):
        assert encoders.hardware_io(encoder) == ([], None)


def test_the_test_encode_runs_what_an_export_would(monkeypatch):
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda command, **_: seen.append(command) or subprocess.CompletedProcess(command, 0))
    assert encoders._works("h264_vaapi") and encoders._works("h264_mf")
    vaapi, mf = seen
    assert vaapi.index("-vaapi_device") < vaapi.index("-i") and vaapi[vaapi.index("-vf") + 1] == "format=nv12,hwupload"
    assert "-qp" in vaapi and "-rate_control" in mf and "-vaapi_device" not in mf and "-vf" not in mf


def test_a_vaapi_export_takes_the_frame_path_with_the_device_the_upload_and_no_pixel_format(monkeypatch):
    from app import render_api
    from app.render_document import validate_document
    from conftest import make_project, text_clip

    captured = []

    def capture(command, *args, **kwargs):
        captured.append(command)
        raise RuntimeError("captured")

    monkeypatch.setattr(render_api, "choose_encoder", lambda codec: "h264_vaapi" if codec == "h264" else None)
    monkeypatch.setattr(render_api.subprocess, "Popen", capture)
    monkeypatch.delenv("FORMCUT_EXPORT_PATH", raising=False)
    project = validate_document(make_project(clips=[text_clip()]))
    with pytest.raises(RuntimeError, match="captured"):
        render_api.export_media(project, "vaapi", lambda f: None, lambda: False, "mp4", "high")
    command = next(c for c in captured if "rawvideo" in c)
    assert command.index("-vaapi_device") < command.index("-i")
    assert command[command.index("-vf") + 1].endswith(",format=nv12,hwupload")
    assert "-pix_fmt" not in command[command.index("-c:v") :]
