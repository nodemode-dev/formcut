"""NTSC project rates (23.976, 29.97, 59.94, 119.88) carried as exact ratios from the document to the file.

A camera set to NTSC records at 24000/1001, 30000/1001, 60000/1001 or 120000/1001. A project at one of those rates is
accepted, kept as the exact ratio, played on its own grid, exported with that ratio as the file's rate and every frame
in it, and written to EDL, FCP 7 XML, FCPXML and OTIO on its grid.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import typing
import uuid
from fractions import Fraction

import numpy as np
import pytest
from app import interchange, rates
from app.main import app
from app.render_document import validate_document
from app.render_stream import RAW_HEADER
from conftest import make_project, text_clip
from fastapi.testclient import TestClient

client = TestClient(app, headers={"x-formcut-local": "1"})
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg and ffprobe")
NTSC = {"23.976": Fraction(24000, 1001), "29.97": Fraction(30000, 1001), "59.94": Fraction(60000, 1001), "119.88": Fraction(120000, 1001)}
WIDTH, HEIGHT, BAR = 384, 216, 3


def _probe(path: str) -> dict:
    command = ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_streams", "-of", "json", path]
    return json.loads(subprocess.run(command, capture_output=True, text=True, check=True).stdout)["streams"][0]


def _bar_clip(folder, rate: str, seconds: float):
    """MPEG-4 Part 2 (in every ffmpeg) with a bar that steps three pixels a frame, so the column names the frame."""
    path = folder / f"bar-{rate.replace('/', '-')}.mp4"
    picture = f"nullsrc=size={WIDTH}x{HEIGHT}:rate={rate}:duration={seconds},format=yuv420p,geq=lum='if(between(X,{BAR}*N,{BAR}*N+{BAR - 1}),235,64)':cb=128:cr=128"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", picture, "-c:v", "mpeg4", "-q:v", "2", str(path)], check=True)
    return path


def _frame_number(frame) -> int:
    return int(np.argmax(np.asarray(frame, np.float64)[..., :3].mean(axis=(0, 2)))) // BAR


@pytest.mark.parametrize(
    ("given", "wanted"),
    [
        ("30000/1001", Fraction(30000, 1001)),
        (29.97, Fraction(30000, 1001)),
        (30000 / 1001, Fraction(30000, 1001)),
        (23.976, Fraction(24000, 1001)),
        (59.94, Fraction(60000, 1001)),
        (119.88, Fraction(120000, 1001)),
        (25, Fraction(25)),
        (30.0, Fraction(30)),
        ("120", Fraction(120)),
    ],
)
def test_a_rate_is_read_as_its_exact_ratio(given, wanted):
    assert rates.exact(given) == wanted


@pytest.mark.parametrize("given", [29.5, 0, 121, 240, "abc", True, float("nan"), None])
def test_a_rate_a_project_cannot_have_is_refused(given):
    with pytest.raises(ValueError):
        rates.exact(given)


@pytest.mark.parametrize("label", list(NTSC))
def test_the_document_keeps_the_exact_ratio(label):
    document = validate_document(make_project(fps=float(label)))
    assert document["fps"] == float(NTSC[label])
    assert rates.exact(document["fps"]) == NTSC[label]
    timeline = make_project(fps=25)
    timeline["timelines"][0]["fps"] = "30000/1001"
    assert validate_document(timeline)["fps"] == 30000 / 1001


def test_a_saved_project_keeps_its_ntsc_rate():
    saved = client.post("/api/projects", json={"title": "ntsc", "fps": 30000 / 1001, "timelines": [{"tracks": []}]})
    assert saved.status_code in (200, 201), saved.text
    assert saved.json()["fps"] == 30000 / 1001


def test_the_agent_tools_and_the_rpc_agree_on_the_rates():
    from app import agent_mcp, automation

    for tool in (agent_mcp.formcut_create_project, agent_mcp.formcut_set_frame):
        limits = typing.get_type_hints(tool, include_extras=True)["fps"].__metadata__[0].metadata
        assert {type(item).__name__: getattr(item, "le", getattr(item, "ge", None)) for item in limits} == {"Ge": 1, "Le": 120}
    created = automation.dispatch("project.create", {"title": "ntsc"})
    edited = automation.dispatch(
        "project.edit",
        {"id": created["id"], "revision": created["revision"], "commands": [{"op": "project.settings", "patch": {"fps": 59.94}}]},
    )
    assert automation.dispatch("project.get", {"id": created["id"]})["fps"] == 60000 / 1001, edited
    with pytest.raises(ValueError):
        automation.dispatch(
            "project.edit",
            {"id": created["id"], "revision": edited["revision"], "commands": [{"op": "project.settings", "patch": {"fps": 240}}]},
        )


@pytest.mark.parametrize("label", ["29.97", "59.94"])
def test_playback_streams_on_the_ntsc_grid(label):
    rate = NTSC[label]
    project = make_project(fps=float(rate), duration=2.0, clips=[text_clip(duration=2.0)])
    session = client.post("/api/render/sessions", json={"project": project, "width": 320}).json()["id"]
    try:
        with client.stream("GET", f"/api/render/sessions/{session}/stream?start=0&fps={float(rate)}&format=raw") as reply:
            assert reply.status_code == 200
            body = reply.read()
    finally:
        client.delete(f"/api/render/sessions/{session}")
    times, at = [], 0
    while at + RAW_HEADER.size <= len(body):
        size, time, _, _ = RAW_HEADER.unpack_from(body, at)
        times.append(time)
        at += RAW_HEADER.size + size
    assert len(times) >= 10
    assert all(abs(t * float(rate) - round(t * float(rate))) < 1e-6 for t in times), times[:5]


@needs_ffmpeg
@pytest.mark.parametrize(("label", "seconds", "frames"), [("29.97", 2.0, 60), ("59.94", 1.0, 60), ("23.976", 1.0, 24)])
def test_an_ntsc_project_exports_at_its_exact_rate_with_every_frame(label, seconds, frames):
    from app.render_api import export_media

    project = make_project(width=320, height=180, fps=float(NTSC[label]), duration=seconds, clips=[text_clip(duration=seconds)])
    result = export_media(project, "ntsc-" + uuid.uuid4().hex, lambda _: None, lambda: False, "mp4", "draft")
    stream = _probe(result["file"])
    assert stream["r_frame_rate"] == stream["avg_frame_rate"] == rates.text(NTSC[label])
    assert int(stream["nb_read_frames"]) == frames


@needs_ffmpeg
@pytest.mark.parametrize(("preset", "frames"), [("23.976", 24), ("59.94", 60)])
def test_a_whole_rate_project_exports_at_an_ntsc_preset(preset, frames):
    """It failed with "Invalid project fps": the preset was written into the project and the document refused it."""
    from app.render_api import export_media

    project = make_project(width=320, height=180, fps=30, duration=1.0, clips=[text_clip(duration=1.0)])
    result = export_media(project, "preset-" + uuid.uuid4().hex, lambda _: None, lambda: False, "mp4", "draft", rate=preset)
    stream = _probe(result["file"])
    assert stream["r_frame_rate"] == rates.text(NTSC[preset])
    assert int(stream["nb_read_frames"]) == frames


@needs_ffmpeg
def test_a_23_976_source_on_a_23_976_timeline_keeps_every_frame(tmp_path, monkeypatch):
    from app import media, proxies
    from app.render_api import export_media
    from app.renderer import FrameRenderer

    monkeypatch.setattr(proxies, "enabled", lambda: False)
    rate = NTSC["23.976"]
    source = _bar_clip(tmp_path, "24000/1001", 2.0)
    count = int(_probe(str(source))["nb_read_frames"])
    assert count == 48
    media_id = media.ingest_path(source, source.name)["id"]
    duration = count / float(rate)
    clip = {"id": "v", "kind": "video", "label": "v", "mediaId": media_id, "start": 0.0, "duration": duration, "sourceIn": 0.0}
    project = make_project(width=WIDTH, height=HEIGHT, fps=float(rate), duration=duration, clips=[clip])
    renderer = FrameRenderer(project)
    try:
        assert [_frame_number(renderer.frame(index / float(rate))) for index in range(count)] == list(range(count))
    finally:
        renderer.close()
    result = export_media(project, "keep-" + uuid.uuid4().hex, lambda _: None, lambda: False, "mp4", "high")
    assert _probe(result["file"])["r_frame_rate"] == "24000/1001"
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", result["file"], "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True
    ).stdout
    written = np.frombuffer(raw, np.uint8).reshape(-1, HEIGHT, WIDTH, 3)
    assert [_frame_number(frame) for frame in written] == list(range(count))


@needs_ffmpeg
def test_a_proxy_of_an_ntsc_source_keeps_its_rate(tmp_path):
    from app import proxies

    source = _bar_clip(tmp_path, "30000/1001", 1.0)
    built = proxies.build_proxy("ntsc-" + uuid.uuid4().hex, source, lambda _: None, lambda: False, 960)
    stream = _probe(str(built))
    assert stream["avg_frame_rate"] == "30000/1001"
    assert int(stream["nb_read_frames"]) == 30


def _timeline_project(rate: Fraction) -> dict:
    fps = float(rate)
    clips = [
        {"id": "a", "kind": "video", "label": "a.mp4", "mediaId": "m1", "start": 0.0, "duration": 300 / fps, "sourceIn": 48 / fps},
        {"id": "b", "kind": "video", "label": "a.mp4", "mediaId": "m1", "start": 300 / fps, "duration": 4500 / fps, "sourceIn": 0.0},
    ]
    project = make_project(fps=fps, duration=4800 / fps, clips=clips)
    return validate_document(project)


MEDIA = [{"id": "m1", "name": "a.mp4", "kind": "video", "duration": 600.0, "width": 1920, "height": 1080, "fps": 29.97}]


def test_the_edl_of_a_29_97_project_comes_back_on_the_same_frames():
    project = _timeline_project(NTSC["29.97"])
    text, report = interchange.export_edl(project, 0)
    assert "FCM: NON-DROP FRAME" in text
    assert report == ["29.97 fps is written as 30 fps non-drop timecode"]
    timeline, problems = interchange.import_edl(text, MEDIA, project["fps"])
    assert not problems
    fps = project["fps"]
    for went, came in zip(project["timelines"][0]["tracks"][0]["clips"], timeline["tracks"][0]["clips"], strict=True):
        for key in ("start", "duration", "sourceIn"):
            assert round(came[key] * fps) == round(went[key] * fps), key


def test_a_drop_frame_edl_is_read_at_29_97():
    """Export writes non-drop timecode only; a drop-frame EDL from elsewhere is read on the drop-frame count."""
    text = "TITLE: df\nFCM: DROP FRAME\n\n001  AX       V     C        00:00:00;00 00:01:00;02 01:00:00;00 01:01:00;02\n* FROM CLIP NAME: a.mp4\n"
    timeline, _ = interchange.import_edl(text, MEDIA, 30000 / 1001)
    clip = timeline["tracks"][0]["clips"][0]
    assert round(clip["duration"] * 30000 / 1001) == 1800


def test_fcp7_xml_and_fcpxml_carry_the_ntsc_rate_and_come_back():
    project = _timeline_project(NTSC["29.97"])
    fcp7, _ = interchange.export_fcp7(project, MEDIA)
    assert "<timebase>30</timebase>" in fcp7 and "<ntsc>TRUE</ntsc>" in fcp7
    fcpxml, _ = interchange.export_fcpxml(project, MEDIA)
    assert 'frameDuration="1001/30000s"' in fcpxml
    fps = project["fps"]
    for back in (interchange.import_fcp7(fcp7, MEDIA)[0], interchange.import_fcpxml(fcpxml, MEDIA)[0]):
        clips = sorted((c for t in back["tracks"] for c in t["clips"]), key=lambda c: c["start"])
        assert [round(c["start"] * fps) for c in clips] == [0, 300]
        assert [round(c["duration"] * fps) for c in clips] == [300, 4500]


def test_otio_carries_the_exact_rate():
    project = _timeline_project(NTSC["23.976"])
    document, _ = interchange.export_otio(project, media=MEDIA)
    found = json.dumps(document)
    assert str(24000 / 1001) in found
