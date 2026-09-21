"""Rotation, crossfades, dips and still images on the layered native path.

A crossfade and a dip are alpha ramps and nothing else in the renderer, so the
layered path takes them; wipes, slides, zooms, irises and dissolves draw more
and keep the frame path. A rotated layer is placed by the box around it, and a
still is fed to ffmpeg exactly as the renderer decodes it.
"""

from __future__ import annotations

import math
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from app.fast_layers import Layer, Plan, graph, inputs, plan, refusal
from conftest import make_project, text_clip
from PIL import Image

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def video(clip_id: str, start: float, duration: float, media_id: str = "m1", **extra) -> dict:
    return {
        "id": clip_id,
        "kind": "video",
        "label": clip_id,
        "mediaId": media_id,
        "start": start,
        "duration": duration,
        "sourceIn": 0.0,
        **extra,
    }


def joined(kind: str, media_id: str = "m1") -> dict:
    later = video("b", 1.5, 1.5, media_id, transitionIn={"type": kind, "duration": 0.6})
    return make_project(width=320, height=180, fps=30, clips=[video("a", 0, 1.5, media_id), later], duration=3.0)


def test_a_crossfade_is_layered():
    assert refusal(joined("crossfade")) is None


def test_a_dip_is_layered():
    assert refusal(joined("dip")) is None


@pytest.mark.parametrize("kind", ["wipe-left", "slide-right", "zoom", "iris", "dissolve"])
def test_transitions_that_draw_more_keep_the_frame_path(kind):
    assert refusal(joined(kind)) is not None


def test_a_rotated_clip_is_layered():
    assert refusal(make_project(clips=[video("a", 0, 2, transform={"rotation": 30})])) is None


def test_a_still_image_is_layered():
    assert refusal(make_project(clips=[{**video("a", 0, 2), "kind": "image"}])) is None


def test_text_still_keeps_the_frame_path():
    assert refusal(make_project(clips=[text_clip()])) == "a text clip"


def layer(**changes) -> Layer:
    base = dict(
        source=Path("/m/a.mp4"),
        rate=30.0,
        width=320,
        height=180,
        seek=0.0,
        shift=0.0,
        span=2.1,
        first=0,
        frames=30,
        lead=0.0,
        duration=1.0,
        x=10,
        y=10,
        w=128,
        h=72,
        flip_h=False,
        flip_v=False,
        opacity=1.0,
        fade_in=0.0,
        fade_out=0.0,
        grade=None,
    )
    return Layer(**{**base, **changes})


def test_a_rotated_layer_turns_onto_a_transparent_box_of_its_own_size():
    text = graph(Plan(320, 180, 30, 30, (0, 0, 0), [layer(angle=0.5, turned_w=174, turned_h=124)]), {}, 320, 180)
    assert "rotate=a=0.50000000:ow=174:oh=124:c=none:bilinear=1" in text


def test_an_unrotated_layer_is_not_turned():
    assert "rotate=" not in graph(Plan(320, 180, 30, 30, (0, 0, 0), [layer()]), {}, 320, 180)


def test_a_still_is_looped_at_the_project_rate_and_not_resampled():
    still = Plan(320, 180, 30, 30, (0, 0, 0), [layer(still=True, span=1.0)])
    assert inputs(still, {0: Path("frames/still0.png")})[:4] == ["-loop", "1", "-framerate", "30"]
    assert graph(still, {}, 320, 180).split(";")[1].startswith("[0:v:0]format=rgba,trim=end_frame=30,setpts=PTS-STARTPTS")


@pytest.fixture(scope="module")
def footage(tmp_path_factory):
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg and ffprobe are needed to encode test media")
    from app import media

    folder = tmp_path_factory.mktemp("more-layers")
    clip = folder / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=4",
            "-f",
            "lavfi",
            "-i",
            "sine=d=4",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        check=True,
    )
    picture = folder / "turned.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.fromarray(np.full((40, 80, 3), 200, np.uint8)).save(picture, exif=exif)
    return media.ingest_path(clip, "clip.mp4")["id"], media.ingest_path(picture, "turned.jpg")["id"]


def planned(project: dict):
    from app.render_document import validate_document

    document = validate_document(project)
    return plan(document, math.ceil(document["duration"] * document["fps"]))


def test_the_outgoing_side_of_a_crossfade_keeps_drawing_through_it(footage):
    layers = planned(joined("crossfade", footage[0])).layers
    outgoing = next(item for item in layers if item.first == 0)
    assert outgoing.frames == round((1.5 + 0.6) * 30) and outgoing.fade_out == 0


def test_the_incoming_side_of_a_crossfade_fades_in_over_it(footage):
    incoming = next(item for item in planned(joined("crossfade", footage[0])).layers if item.first == 45)
    assert incoming.fade_in == pytest.approx(0.6)


def test_a_dip_fades_each_side_over_half_its_length(footage):
    layers = planned(joined("dip", footage[0])).layers
    outgoing, incoming = sorted(layers, key=lambda item: item.first)
    assert outgoing.fade_out == pytest.approx(0.3) and incoming.fade_in == pytest.approx(0.3)


def test_a_rotated_layer_is_placed_by_the_box_around_it(footage):
    project = make_project(
        width=320, height=180, fps=30, clips=[video("a", 0, 1, footage[0], transform={"scale": 50, "rotation": 90})], duration=1.0
    )
    placed = planned(project).layers[0]
    assert (placed.turned_w, placed.turned_h) == (90, 160) and (placed.x, placed.y) == (115, 10)


def test_an_image_is_placed_by_its_upright_size(footage):
    project = make_project(width=320, height=180, fps=30, clips=[{**video("i", 0, 1, footage[1]), "kind": "image"}], duration=1.0)
    placed = planned(project).layers[0]
    assert placed.still and (placed.width, placed.height) == (40, 80)


def both(project: dict, name: str, monkeypatch) -> tuple[dict, dict]:
    from app.render_api import export_media
    from app.render_document import validate_document

    results = []
    for route in ("", "frames"):
        monkeypatch.setenv("FORMCUT_EXPORT_PATH", route)
        results.append(
            export_media(validate_document(project), f"{name}-{route or 'layered'}", lambda f: None, lambda: False, "webm", "high")
        )
    return results[0], results[1]


def psnr(first: str, second: str) -> float:
    report = subprocess.run(
        ["ffmpeg", "-i", first, "-i", second, "-lavfi", "[0:v][1:v]psnr", "-f", "null", "-"], capture_output=True, text=True, check=True
    ).stderr
    value = re.search(r"average:([0-9.]+|inf)", report).group(1)
    return math.inf if value == "inf" else float(value)


def test_a_crossfade_exports_natively_close_to_the_frame_path(footage, monkeypatch):
    layered, frames = both(joined("crossfade", footage[0]), "crossfade", monkeypatch)
    assert layered["renderPath"] == "layered" and psnr(frames["file"], layered["file"]) > 40


def test_a_rotated_picture_in_picture_exports_natively_within_sight(footage, monkeypatch):
    clips = [video("top", 0, 1, footage[0], transform={"scale": 40, "posX": 20, "rotation": 20})]
    project = make_project(width=320, height=180, fps=30, clips=clips, duration=1.0)
    project["timelines"][0]["tracks"].append({"id": "t1", "name": "V2", "clips": [video("base", 0, 1, footage[0])]})
    layered, frames = both(project, "rotated", monkeypatch)
    assert layered["renderPath"] == "layered" and psnr(frames["file"], layered["file"]) > 28
