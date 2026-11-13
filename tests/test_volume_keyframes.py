"""Volume written as clip keyframes reaches the mix that is heard and exported.

The ducking helper writes `keyframes[].props.volume`; the mix used to read only
`volumeKeys`, so every duck was dropped from the preview mix and from the file.
"""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest
from app.timing import volume_at
from conftest import make_project

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
RATE = 48000
DUCK = [
    {"t": 0.0, "props": {"volume": 1.0}},
    {"t": 1.0, "props": {"volume": 1.0}},
    {"t": 1.2, "props": {"volume": 0.2}},
    {"t": 1.8, "props": {"volume": 0.2}},
    {"t": 2.0, "props": {"volume": 1.0}},
]


def clip(**extra) -> dict:
    return {"id": "a", "kind": "video", "label": "a", "mediaId": "m1", "start": 0.0, "duration": 3.0, "sourceIn": 0.0, **extra}


def test_a_clip_without_keys_keeps_its_fixed_volume():
    assert volume_at(clip(volume=0.5), 1.5) == 0.5


def test_volume_keys_are_unchanged():
    keyed = clip(volume=0.5, volumeKeys=[{"t": 0, "value": 1.0}, {"t": 2, "value": 0.0}])
    assert volume_at(keyed, 1.0) == pytest.approx(0.5)
    assert volume_at(keyed, 3.0) == 0.0


def test_keyframed_volume_dips_and_comes_back():
    ducked = clip(keyframes=DUCK)
    assert volume_at(ducked, 0.5) == 1.0
    assert volume_at(ducked, 1.1) == pytest.approx(0.6)
    assert volume_at(ducked, 1.5) == pytest.approx(0.2)
    assert volume_at(ducked, 2.5) == 1.0


def test_keyframed_volume_scales_the_clips_own_volume():
    assert volume_at(clip(volume=0.5, keyframes=DUCK), 1.5) == pytest.approx(0.1)
    assert volume_at(clip(volume=0.5, keyframes=DUCK), 0.5) == pytest.approx(0.5)


def test_keyframed_volume_scales_volume_keys_when_both_are_written():
    both = clip(volumeKeys=[{"t": 0, "value": 0.5}], keyframes=DUCK)
    assert volume_at(both, 1.5) == pytest.approx(0.1)


def test_keyframes_on_the_picture_leave_the_volume_alone():
    assert volume_at(clip(volume=0.8, keyframes=[{"t": 0, "props": {"scale": 100}}, {"t": 1, "props": {"scale": 150}}]), 0.5) == 0.8


@pytest.fixture(scope="module")
def tone(tmp_path_factory):
    if not HAVE_FFMPEG:
        pytest.skip("ffmpeg and ffprobe are needed to encode test media")
    from app import media

    path = tmp_path_factory.mktemp("tone") / "tone.mp4"
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
            "sine=frequency=440:duration=3",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            str(path),
        ],
        check=True,
    )
    return media.ingest_path(path, "tone.mp4")["id"]


def project_for(media_id: str, **extra) -> dict:
    return make_project(width=320, height=180, fps=30, duration=3.0, clips=[clip(mediaId=media_id, **extra)])


def level(samples: np.ndarray, start: float, end: float) -> float:
    part = samples[int(start * RATE) : int(end * RATE)]
    return float(np.sqrt(np.mean(np.square(part))))


def exported_sound(path: str) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-map", "0:a", "-f", "f32le", "-ac", "1", "-ar", str(RATE), "pipe:1"],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(raw, "<f4")


def test_the_mix_follows_keyframed_volume(tone):
    from app.audio_render import mix_audio
    from app.render_document import validate_document

    mix = mix_audio(validate_document(project_for(tone, keyframes=DUCK)))[:, 0]
    assert level(mix, 1.3, 1.7) / level(mix, 0.2, 0.8) == pytest.approx(0.2, abs=0.02)


@pytest.mark.parametrize("route", ["", "frames"])
def test_an_export_ducks_where_the_keyframes_dip(tone, monkeypatch, route):
    from app.encoders import choose
    from app.render_api import export_media
    from app.render_document import validate_document

    monkeypatch.setenv("FORMCUT_EXPORT_PATH", route)
    container = "mp4" if choose("h264") else "webm"
    result = export_media(
        validate_document(project_for(tone, keyframes=DUCK)), f"duck-{route or 'native'}", lambda _: None, lambda: False, container, "high"
    )
    assert result["renderPath"] == (route or "native")
    sound = exported_sound(result["file"])
    assert level(sound, 1.3, 1.7) / level(sound, 0.2, 0.8) == pytest.approx(0.2, abs=0.03)
    assert level(sound, 2.2, 2.8) / level(sound, 0.2, 0.8) == pytest.approx(1.0, abs=0.05)


def test_a_document_with_keyframed_volume_is_accepted_and_bounded():
    from app.render_document import validate_document

    validate_document(project_for("m1", keyframes=DUCK))
    with pytest.raises(ValueError, match="volume keyframe"):
        validate_document(project_for("m1", keyframes=[{"t": 0, "props": {"volume": 9}}]))
