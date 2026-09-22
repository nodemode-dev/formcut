"""Effects switch off without losing their settings; the keyframe toggle stays where it can be seen."""

import json
import os
import pathlib
import re

import numpy as np
import pytest
from PIL import Image

UI = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "src" / "ui"


@pytest.fixture(scope="module")
def picture(tmp_path_factory):
    from app import media

    path = tmp_path_factory.mktemp("switch") / "picture.png"
    ramp = np.linspace(40, 220, 96, dtype=np.uint8)
    Image.fromarray(np.dstack([np.tile(ramp, (54, 1))] * 3)).save(path)
    return media.ingest_path(path, "picture.png")["id"]


def _frame(media_id, effects):
    from app.renderer import FrameRenderer
    from conftest import make_project

    clip = {"id": "a", "kind": "image", "label": "a", "mediaId": media_id, "start": 0, "duration": 1.0, "effects": effects}
    renderer = FrameRenderer(make_project(width=96, height=54, fps=30, duration=1.0, clips=[clip]))
    try:
        return np.asarray(renderer.frame(0.5)).copy()
    finally:
        renderer.close()


def test_an_effect_switched_off_renders_as_no_effect_and_on_again_as_itself(picture):
    vignette = {"id": "vignette", "amount": 1, "params": {}}
    plain, on = _frame(picture, []), _frame(picture, [vignette])
    assert not np.array_equal(plain, on)
    assert np.array_equal(_frame(picture, [{**vignette, "enabled": False}]), plain)
    assert np.array_equal(_frame(picture, [{**vignette, "enabled": True}]), on)


def test_older_projects_without_the_flag_keep_their_effects(picture):
    assert not np.array_equal(_frame(picture, [{"id": "vignette", "amount": 1}]), _frame(picture, []))


def test_the_keyframe_toggle_lives_in_the_track_header_not_the_hidden_keyframe_head():
    source = (UI / "track-keyframes.ts").read_text(encoding="utf-8")
    assert "head.prepend(toggle)" not in source
    assert "lane.previousElementSibling?.append(toggle)" in source
    assert "controls.append(block.toggle)" in source


def test_each_applied_effect_row_has_a_switch():
    source = (UI / "creator-panel.ts").read_text(encoding="utf-8")
    assert "data-power" in source and "next[index].enabled = next[index].enabled === false" in source
    assert os.path.exists(UI / "creator-panel.ts")


def test_every_label_on_an_effect_row_is_translated_in_every_language_and_in_the_row():
    i18n = UI.parent / "i18n"
    rows = (i18n / "language-pack.ts").read_text(encoding="utf-8").split("`")[1].splitlines()
    pack = {row.split("|")[0]: row.split("|")[1:] for row in rows if row}
    inline = (i18n / "text.ts").read_text(encoding="utf-8")
    english = json.loads((i18n / "en.json").read_text(encoding="utf-8"))
    source = (UI / "creator-panel.ts").read_text(encoding="utf-8")
    for phrase in ("Strength", "Up", "Move earlier", "Remove", "Turn off", "Turn on"):
        assert phrase in pack and len(pack[phrase]) == 9 and all(pack[phrase]), phrase
        for language in ("de", "es"):
            table = json.loads((i18n / f"{language}.json").read_text(encoding="utf-8"))
            keyed = any(value == phrase and key in table for key, value in english.items())
            assert keyed or re.search(rf'{language}: \{{[^}}]*"{re.escape(phrase)}":', inline), (language, phrase)
        assert f'phrase("{phrase}")' in source, phrase
