"""The layered native export.

It takes video on several tracks, placed, faded and graded, and refuses
anything else, which keeps the frame path. These check both lists, the graph
each feature becomes, that a grade is baked by the renderer's own code, and on
real encoded media that its pictures are within sight of the frame path's.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
from app import fast_export
from app.fast_layers import LIMIT, Layer, Plan, bake, graph, refusal
from conftest import DECODER_PARITY, make_project, text_clip

GRADE = {"exposure": 0.2, "contrast": 12, "saturation": 15}


def video(clip_id: str = "a", start: float = 0.0, duration: float = 2.0, **extra) -> dict:
    return {
        "id": clip_id,
        "kind": "video",
        "label": clip_id,
        "mediaId": "m1",
        "start": start,
        "duration": duration,
        "sourceIn": 0.0,
        **extra,
    }


def stacked(*tracks: list[dict], background=None) -> dict:
    project = make_project(clips=tracks[0], background=background)
    project["timelines"][0]["tracks"] += [{"id": f"t{i}", "name": "V", "clips": clips} for i, clips in enumerate(tracks[1:], 1)]
    return project


def test_overlapping_clips_keep_the_cut_path_but_are_layered_here():
    project = stacked([video("a")], [video("b", 0.5)])
    assert fast_export.refusal(project) == "clips share a frame" and refusal(project) is None


def test_a_graded_clip_is_layered():
    assert refusal(stacked([video(colour=GRADE)])) is None


def test_a_clip_with_a_lut_is_layered():
    assert refusal(stacked([video(lutId="warm", lutIntensity=0.5)])) is None


def test_fades_are_layered():
    assert refusal(stacked([video(fadeIn=0.5, fadeOut=0.5)])) is None


def test_a_placed_and_faded_picture_in_picture_is_layered():
    assert refusal(stacked([video(transform={"scale": 40, "posX": 25, "posY": -20, "opacity": 70, "flipH": True})])) is None


def test_a_rotated_and_flipped_clip_is_layered():
    assert refusal(stacked([video(transform={"rotation": 10, "flipH": True})])) is None


def test_a_blend_mode_keeps_the_frame_path():
    assert refusal(stacked([video(transform={"blendMode": "Screen"})])) == "blendMode"


def test_effects_keep_the_frame_path():
    assert refusal(stacked([video(effects=[{"id": "blur", "amount": 1}])])) == "effects"


def test_a_mask_keeps_the_frame_path():
    assert refusal(stacked([video(mask={"shape": "rect"})])) == "mask"


def test_text_keeps_the_frame_path():
    assert refusal(stacked([text_clip()])) == "a text clip"


def test_a_graded_image_is_layered():
    assert refusal(stacked([{**video(colour=GRADE), "kind": "image"}])) is None


def test_keyframed_motion_keeps_the_frame_path():
    assert refusal(stacked([video(keyframes=[{"t": 0, "props": {"posX": 0}}, {"t": 1, "props": {"posX": 20}}])])) == "keyframes"


def test_a_wipe_keeps_the_frame_path():
    assert refusal(stacked([video("a", 0, 2), video("b", 2, 2, transitionIn={"type": "wipe-up", "duration": 0.5})])) == "transition"


def test_a_solid_background_is_layered_and_a_gradient_is_not():
    assert refusal(stacked([video()], background="#204060")) is None
    assert refusal(stacked([video()], background={"type": "gradient", "from": "#000", "to": "#fff"})) == "background"


def test_more_layers_than_one_graph_takes_keep_the_frame_path():
    assert refusal(stacked(*[[video(f"c{i}")] for i in range(LIMIT + 1)])) == "more layers than one graph takes"


def layer(**changes) -> Layer:
    base = dict(
        source=Path("/m/a.mp4"),
        rate=30.0,
        width=640,
        height=360,
        seek=0.0,
        shift=0.0,
        span=2.1,
        first=6,
        frames=30,
        lead=0.0,
        duration=1.0,
        x=40,
        y=20,
        w=256,
        h=144,
        flip_h=False,
        flip_v=False,
        opacity=1.0,
        fade_in=0.0,
        fade_out=0.0,
        grade=None,
    )
    return Layer(**{**base, **changes})


def plan_of(*layers: Layer, background=(0, 0, 0)) -> Plan:
    return Plan(640, 360, 30, 60, background, list(layers))


def test_a_layer_is_scaled_and_placed_where_the_renderer_puts_it():
    text = graph(plan_of(layer()), {}, 640, 360)
    assert "scale=256:144:flags=bilinear" in text and "overlay=x=40:y=20:format=rgb" in text


def test_a_layer_starts_on_its_own_first_frame():
    assert "setpts=PTS-STARTPTS+6/(30*TB)" in graph(plan_of(layer()), {}, 640, 360)


def test_a_graded_layer_applies_its_baked_cube():
    text = graph(plan_of(layer(grade={"colour": GRADE})), {0: Path("grades/grade0.cube")}, 640, 360)
    assert "lut3d=file='grades/grade0.cube':interp=trilinear" in text


def test_an_ungraded_layer_has_no_cube():
    assert "lut3d" not in graph(plan_of(layer()), {}, 640, 360)


def test_opacity_scales_the_alpha():
    assert "colorchannelmixer=aa=0.700000" in graph(plan_of(layer(opacity=0.7)), {}, 640, 360)


def test_fades_run_on_the_clips_own_time():
    text = graph(plan_of(layer(lead=0.02, fade_in=0.4, fade_out=0.3)), {}, 640, 360)
    assert "setpts=PTS-STARTPTS+0.020000/TB" in text
    assert "fade=t=in:st=0:d=0.400000:alpha=1" in text and "fade=t=out:st=0.700000:d=0.300000:alpha=1" in text


def test_flips_mirror_the_layer():
    text = graph(plan_of(layer(flip_h=True, flip_v=True)), {}, 640, 360)
    assert "hflip" in text and "vflip" in text


def test_the_background_is_the_projects_colour():
    assert graph(plan_of(background=(32, 64, 96)), {}, 640, 360).startswith("color=c=0x204060:s=640x360:r=30")


def test_layers_are_overlaid_in_order():
    text = graph(plan_of(layer(), layer()), {}, 640, 360)
    assert text.index("[base0][layer0]overlay") < text.index("[base1][layer1]overlay") and "[base2]scale=640:360" in text


def test_a_neutral_grade_bakes_to_the_identity(tmp_path):
    lines = bake({"colour": {}}, tmp_path / "neutral.cube").read_text().splitlines()
    values = np.array([[float(v) for v in line.split()] for line in lines[1:]])
    steps = np.round(np.linspace(0, 255, 33)) / 255
    assert lines[0] == "LUT_3D_SIZE 33" and len(values) == 33**3
    assert np.allclose(values[:33, 0], steps, atol=1 / 255) and np.allclose(values[::33, 1][:33], steps, atol=1 / 255)


def test_a_grade_bakes_to_what_the_renderer_draws(tmp_path):
    from app.pixel_effects import apply_colour_panel

    lines = bake({"colour": GRADE}, tmp_path / "grade.cube").read_text().splitlines()
    corner = [float(v) for v in lines[-1].split()]
    white = apply_colour_panel(np.full((1, 1, 4), 255, np.uint8), GRADE)[0, 0, :3] / 255
    assert corner == pytest.approx(list(white), abs=1e-6)


@pytest.fixture(scope="module")
def footage(tmp_path_factory):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg and ffprobe are needed to encode test media")
    from app import media

    path = tmp_path_factory.mktemp("layers") / "source.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=30:duration=3",
            "-f",
            "lavfi",
            "-i",
            "sine=d=3",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
    )
    return media.ingest_path(path, "source.mp4")["id"]


def export(project: dict, name: str, route: str, monkeypatch) -> dict:
    from app.render_api import export_media
    from app.render_document import validate_document

    monkeypatch.setenv("FORMCUT_EXPORT_PATH", route)
    return export_media(validate_document(project), f"{name}-{route or 'layered'}", lambda fraction: None, lambda: False, "webm", "high")


def three_layers(media_id: str) -> dict:
    def clip(clip_id: str, start: float = 0.0, duration: float = 2.0, **extra) -> dict:
        return {**video(clip_id, start, duration), "mediaId": media_id, **extra}

    project = stacked(
        [clip("top", start=0.3, duration=1.2, transform={"scale": 40, "posX": 28, "posY": -28}, fadeIn=0.3)],
        [clip("middle", colour=GRADE, transform={"scale": 40, "posX": -28, "posY": 28, "opacity": 80})],
        [clip("bottom", colour=GRADE)],
    )
    project.update(width=320, height=180, fps=30, duration=2.0)
    return project


@DECODER_PARITY
def test_layers_export_natively_within_sight_of_the_frame_path(footage, monkeypatch):
    layered = export(three_layers(footage), "stack", "", monkeypatch)
    frames = export(three_layers(footage), "stack", "frames", monkeypatch)
    assert layered["renderPath"] == "layered" and frames["renderPath"] == "frames"
    report = subprocess.run(
        ["ffmpeg", "-i", frames["file"], "-i", layered["file"], "-lavfi", "[0:v][1:v]psnr", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stderr
    assert float(re.search(r"average:([0-9.]+|inf)", report).group(1)) > 30


def test_a_cut_only_timeline_still_takes_the_exact_cut_path(footage, monkeypatch):
    project = stacked([{**video("a", 0, 1.0), "mediaId": footage}])
    project.update(width=320, height=180, fps=30, duration=1.0)
    assert export(project, "cut", "", monkeypatch)["renderPath"] == "native"
