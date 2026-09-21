"""The native export path.

It may only take a timeline whose every output frame it can reproduce, so most
of these check what it refuses. The rest check the frame arithmetic, the graph
it builds, and, on real encoded media, that its pictures are the frame path's.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from app import fast_export
from app.fast_export import LIMIT, Plan, Segment, _span, _timebase, graph, inputs, refusal
from conftest import ROOT, make_project, text_clip

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


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


def verdict(*clips: dict, background=None) -> str | None:
    return refusal(make_project(clips=list(clips), background=background))


def two_tracks(upper: list[dict], lower: list[dict]) -> dict:
    project = make_project(clips=upper)
    project["timelines"][0]["tracks"].append({"id": "t1", "name": "V2", "clips": lower})
    return project


def test_a_plain_video_clip_is_taken():
    assert verdict(video()) is None


def test_an_empty_timeline_is_taken_as_black():
    assert verdict() is None


def test_audio_clips_do_not_count_against_it():
    assert verdict(video(), {"id": "s", "kind": "audio", "mediaId": "m2", "start": 0.0, "duration": 2.0, "volume": 0.5}) is None


def test_a_hidden_track_is_ignored_whatever_it_holds():
    project = two_tracks([video()], [text_clip(clip_id="t", duration=2.0)])
    project["timelines"][0]["tracks"][1]["hidden"] = True
    assert refusal(project) is None


def test_a_text_clip_is_refused():
    assert verdict(text_clip()) == "a text clip"


def test_an_image_clip_is_refused():
    assert verdict({**video(), "kind": "image"}) == "a image clip"


def test_a_filter_clip_is_refused():
    assert verdict({**video(), "kind": "filter"}) == "a filter clip"


def test_a_video_clip_without_media_is_refused():
    assert verdict({**video(), "mediaId": ""}) == "a clip without media"


def test_effects_are_refused():
    assert verdict(video(effects=[{"id": "blur", "amount": 1}])) == "effects"


def test_a_legacy_effect_is_refused():
    assert verdict(video(effectId="sepia")) == "effectId"


def test_a_lut_is_refused():
    assert verdict(video(lutId="warm")) == "lutId"


def test_a_custom_shader_is_refused():
    assert verdict(video(shaderId="glow")) == "shaderId"


def test_a_mask_is_refused():
    assert verdict(video(mask={"shape": "rect"})) == "mask"


def test_a_cutout_is_refused():
    assert verdict(video(cutout={"enabled": True})) == "cutout"


def test_a_chroma_key_is_refused():
    assert verdict(video(key={"colour": "#00ff00"})) == "key"


def test_stabilisation_is_refused():
    assert verdict(video(stabilise={"strength": 1})) == "stabilise"


def test_the_colour_panel_is_refused():
    assert verdict(video(colour={"exposure": 0.5})) == "colour"


def test_a_crop_is_refused():
    assert verdict(video(crop={"left": 0.1})) == "crop"


def test_smooth_slow_motion_is_refused_because_it_makes_frames():
    assert verdict(video(smoothSlow=True)) == "smoothSlow"


def test_a_reversed_clip_is_refused():
    assert verdict(video(reversed=True)) == "reversed"


def test_a_speed_curve_is_refused():
    assert verdict(video(speedCurve=[[0, 1], [1, 2]])) == "speedCurve"


def test_animation_slots_are_refused():
    assert verdict(video(animations=[{"slot": "in", "preset": "zoom"}])) == "animations"


def test_a_visual_fade_in_is_refused():
    assert verdict(video(fadeIn=0.5)) == "fadeIn"


def test_a_visual_fade_out_is_refused():
    assert verdict(video(fadeOut=0.5)) == "fadeOut"


def test_a_crossfade_is_refused_on_both_sides():
    first = video("a", 0.0, 2.0)
    second = video("b", 2.0, 2.0, transitionIn={"type": "crossfade", "duration": 0.5})
    assert verdict(first, second) is not None


def test_a_dip_transition_is_refused():
    first = video("a", 0.0, 2.0)
    second = video("b", 2.0, 2.0, transitionIn={"type": "dip", "duration": 0.5})
    assert verdict(first, second) is not None


def test_double_speed_is_refused():
    assert verdict(video(speed=2)) == "speed"


def test_half_speed_is_refused():
    assert verdict(video(speed=0.5)) == "speed"


def test_normal_speed_written_out_is_taken():
    assert verdict(video(speed=1)) is None


def test_scale_is_refused():
    assert verdict(video(transform={"scale": 120})) == "transform"


def test_position_is_refused():
    assert verdict(video(transform={"posX": 10})) == "transform"


def test_rotation_is_refused():
    assert verdict(video(transform={"rotation": 90})) == "transform"


def test_opacity_is_refused():
    assert verdict(video(transform={"opacity": 50})) == "transform"


def test_a_horizontal_flip_is_refused():
    assert verdict(video(transform={"flipH": True})) == "transform"


def test_a_vertical_flip_is_refused():
    assert verdict(video(transform={"flipV": True})) == "transform"


def test_a_blend_mode_is_refused():
    assert verdict(video(transform={"blendMode": "Screen"})) == "transform"


def test_a_stretched_width_is_refused():
    assert verdict(video(transform={"width": 80})) == "transform"


def test_a_transform_written_out_at_its_defaults_is_taken():
    assert verdict(video(transform={"scale": 100, "posX": 0, "opacity": 100, "blendMode": "Normal"})) is None


def test_keyframes_on_the_picture_are_refused():
    assert verdict(video(keyframes=[{"t": 0, "props": {"scale": 100}}, {"t": 1, "props": {"scale": 150}}])) == "keyframes"


def test_keyframes_on_sound_alone_are_taken():
    assert verdict(video(keyframes=[{"t": 0, "props": {"volume": 1}}, {"t": 1, "props": {"volume": 0}}])) is None


def test_an_expression_on_the_picture_is_refused():
    assert verdict(video(expressions={"opacity": "50 + 50 * sin(t)"})) == "expressions"


def test_an_empty_expression_table_is_taken():
    assert verdict(video(expressions={})) is None


def test_a_black_background_written_as_text_is_taken():
    assert verdict(video(), background="#000000") is None


def test_a_black_background_written_as_a_fill_is_taken():
    assert verdict(video(), background={"type": "colour", "colour": "#000"}) is None


def test_a_coloured_background_is_refused():
    assert verdict(video(), background="#ff0000") == "background"


def test_a_gradient_background_is_refused():
    assert verdict(video(), background={"type": "gradient", "from": "#000000", "to": "#ffffff"}) == "background"


def test_a_blurred_background_is_refused():
    assert verdict(video(), background={"type": "blur", "amount": 40}) == "background"


def test_clips_that_share_a_frame_across_tracks_are_refused():
    assert refusal(two_tracks([video("a", 0.0, 2.0)], [video("b", 1.0, 2.0)])) == "clips share a frame"


def test_clips_on_two_tracks_that_never_meet_are_taken():
    assert refusal(two_tracks([video("a", 0.0, 1.0)], [video("b", 1.0, 2.0)])) is None


def test_clips_that_touch_end_to_start_are_taken():
    assert verdict(video("a", 0.0, 1.0), video("b", 1.0, 1.0)) is None


def test_more_clips_than_one_graph_takes_are_refused():
    clips = [video(f"c{i}", i * 0.05, 0.05) for i in range(LIMIT + 1)]
    project = make_project(clips=clips, duration=(LIMIT + 1) * 0.05)
    assert refusal(project) == "more clips than one graph takes"


def test_a_clip_is_drawn_from_its_first_frame_to_the_frame_before_its_end():
    assert _span(video("a", 0.0, 1.0), 30, 120) == (0, 30)


def test_a_clip_starting_between_frames_begins_on_the_next_frame():
    assert _span(video("a", 0.51, 1.0), 30, 120) == (16, 46)


def test_a_span_stops_at_the_last_frame_of_the_export():
    assert _span(video("a", 3.5, 2.0), 30, 120) == (105, 120)


def test_a_clip_shorter_than_a_frame_gap_draws_nothing():
    first, end = _span(video("a", 0.101, 0.01), 30, 120)
    assert first == end


def test_a_span_matches_the_renderers_own_test_at_every_frame():
    clip = video("a", 0.1, 0.2)
    first, end = _span(clip, 30, 30)
    drawn = [i for i in range(30) if 0 <= i / 30 - clip["start"] < clip["duration"]]
    assert list(range(first, end)) == drawn


def test_the_timebase_fits_a_signed_32_bit_denominator():
    assert _timebase(60000 / 1001, 120) < 2**31


def test_the_timebase_holds_the_source_and_output_grids_exactly():
    ticks = _timebase(30000 / 1001, 30)
    assert ticks % (30000 * 30) == 0


def plan_with(*segments: Segment, width: int = 320, height: int = 180) -> Plan:
    return Plan(width, height, 30, sum(s.frames for s in segments), list(segments))


def test_a_gap_is_black_for_exactly_its_frames():
    text = graph(plan_with(Segment(15)), 320, 180)
    assert "color=c=black:s=320x180:r=30" in text and "trim=end_frame=15" in text


def test_every_source_is_sought_where_the_decoder_would_seek():
    plan = plan_with(Segment(30, Path("/m/a.mp4"), 30.0, 320, 180, 1.5, 0.0, 1.2))
    assert inputs(plan) == ["-ss", "1.5", "-t", "1.200000", "-i", "/m/a.mp4"]


def test_a_source_at_the_canvas_size_is_not_rescaled():
    text = graph(plan_with(Segment(30, Path("/m/a.mp4"), 30.0, 320, 180, 0.0, 0.0, 1.1)), 320, 180)
    assert ":flags=bilinear" not in text and "pad=320:180:0:0" in text


def test_a_narrower_source_is_letterboxed_in_the_middle():
    text = graph(plan_with(Segment(30, Path("/m/a.mp4"), 30.0, 240, 180, 0.0, 0.0, 1.1)), 320, 180)
    assert "scale=240:180" in text and "pad=320:180:40:0" in text


def test_a_slot_shows_the_latest_frame_at_or_before_it():
    text = graph(plan_with(Segment(30, Path("/m/a.mp4"), 24.0, 320, 180, 0.0, 0.01, 1.1)), 320, 180)
    assert "fps=30:round=up" in text


def test_the_output_is_sized_the_way_the_frame_path_sizes_it():
    text = graph(plan_with(Segment(10)), 640, 360)
    assert text.endswith("concat=n=1:v=1:a=0,scale=640:360,pad=ceil(iw/2)*2:ceil(ih/2)*2[out]")


def test_segments_are_concatenated_in_order():
    plan = plan_with(Segment(5), Segment(30, Path("/m/a.mp4"), 30.0, 320, 180, 0.0, 0.0, 1.1), Segment(5))
    assert "[s0][s1][s2]concat=n=3" in graph(plan, 320, 180)


def clip_keys(path: Path) -> set[str]:
    return set(re.findall(r'clip(?:\.get\(|\[)"([A-Za-z_]+)"', path.read_text(encoding="utf-8")))


def test_every_clip_key_the_renderer_reads_is_known_to_the_native_path():
    known = set(fast_export.ABSENT) | {
        "id",
        "kind",
        "label",
        "mediaId",
        "start",
        "duration",
        "sourceIn",
        "trackIndex",
        "trackHidden",
        "muted",
        "speed",
        "transform",
        "keyframes",
        "expressions",
        "lutIntensity",
        "textStyle",
        "volume",
        "volumeKeys",
    }
    app = ROOT / "backend" / "app"
    read = clip_keys(app / "renderer.py") | clip_keys(app / "timing.py")
    assert read - known == set(), "teach fast_export.py whether these change the picture"


@pytest.fixture(scope="module")
def sources(tmp_path_factory):
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg and ffprobe are needed to encode test media")
    from app import media

    folder = tmp_path_factory.mktemp("sources")
    made = {}
    for name, size, rate in (("r24", "320x180", 24), ("wide", "320x240", 30)):
        path = folder / f"{name}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"testsrc2=size={size}:rate={rate}:duration=3",
                "-f",
                "lavfi",
                "-i",
                "sine=d=3",
                "-pix_fmt",
                "yuv420p",
                "-shortest",
                str(path),
            ],
            check=True,
        )
        made[name] = media.ingest_path(path, f"{name}.mp4")["id"]
    return made


def export(project: dict, name: str, route: str, monkeypatch) -> dict:
    from app.encoders import choose
    from app.render_api import export_media
    from app.render_document import validate_document

    monkeypatch.setenv("FORMCUT_EXPORT_PATH", route)
    container = "mp4" if choose("h264") else "webm"
    return export_media(validate_document(project), f"{name}-{route or 'native'}", lambda _: None, lambda: False, container, "high")


def decoded(path: str) -> list[str]:
    report = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-map", "0:v", "-f", "framemd5", "-"], capture_output=True, text=True, check=True
    ).stdout
    return [line.rsplit(",", 1)[-1].strip() for line in report.splitlines() if not line.startswith("#")]


def cuts(sources: dict) -> dict:
    clips = [
        {**video("a", 0.2, 1.1), "mediaId": sources["r24"], "sourceIn": 0.537},
        {**video("b", 1.5, 1.0), "mediaId": sources["r24"], "sourceIn": 1.9},
    ]
    return make_project(width=320, height=180, fps=30, clips=clips, duration=2.5)


def test_native_cuts_with_off_grid_timing_are_the_frame_paths_pictures(sources, monkeypatch):
    native = export(cuts(sources), "cuts", "", monkeypatch)
    frames = export(cuts(sources), "cuts", "frames", monkeypatch)
    assert native["renderPath"] == "native" and frames["renderPath"] == "frames"
    assert decoded(native["file"]) == decoded(frames["file"])


def test_a_native_export_has_every_frame_it_promised(sources, monkeypatch):
    result = export(cuts(sources), "count", "", monkeypatch)
    assert len(decoded(result["file"])) == result["frames"] == 75


def test_a_native_export_keeps_the_timelines_sound(sources, monkeypatch):
    result = export(cuts(sources), "sound", "", monkeypatch)
    streams = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", result["file"]],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "audio" in streams.split()


def test_a_letterboxed_source_is_within_sight_of_the_frame_path(sources, monkeypatch):
    project = make_project(
        width=320, height=180, fps=30, clips=[{**video("a", 0.0, 1.0), "mediaId": sources["wide"], "sourceIn": 0.5}], duration=1.0
    )
    native = export(project, "box", "", monkeypatch)
    frames = export(project, "box", "frames", monkeypatch)
    report = subprocess.run(
        ["ffmpeg", "-i", frames["file"], "-i", native["file"], "-lavfi", "[0:v][1:v]psnr", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stderr
    average = float(re.search(r"average:([0-9.]+|inf)", report).group(1))
    assert average > 38


def test_the_frame_path_can_be_chosen_by_setting(sources, monkeypatch):
    assert export(cuts(sources), "chosen", "frames", monkeypatch)["renderPath"] == "frames"


def test_a_timeline_the_native_path_refuses_still_exports(sources, monkeypatch):
    project = make_project(width=320, height=180, fps=30, clips=[text_clip(duration=1.0)], duration=1.0)
    assert export(project, "refused", "", monkeypatch)["renderPath"] == "frames"


def test_a_plan_puts_black_where_nothing_plays(sources):
    from app.render_document import validate_document

    plan = fast_export.plan(validate_document(cuts(sources)), 75)
    assert [(s.frames, s.source is None) for s in plan.segments] == [(6, True), (33, False), (6, True), (30, False)]


def test_a_plan_without_its_media_falls_back(sources):
    from app.render_document import validate_document

    project = make_project(width=320, height=180, fps=30, clips=[{**video(), "mediaId": "missing"}], duration=2.0)
    assert fast_export.plan(validate_document(project), 60) is None


def test_the_native_path_never_leaves_its_encoder_running(sources, monkeypatch):
    before = (
        subprocess.run(["pgrep", "-c", "-x", "ffmpeg"], capture_output=True, text=True, check=False).stdout.strip()
        if os.name != "nt"
        else ""
    )
    export(cuts(sources), "tidy", "", monkeypatch)
    after = (
        subprocess.run(["pgrep", "-c", "-x", "ffmpeg"], capture_output=True, text=True, check=False).stdout.strip()
        if os.name != "nt"
        else ""
    )
    assert after == before
