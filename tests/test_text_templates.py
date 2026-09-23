"""Animated titles (text_templates.py), and the rules both built-in libraries keep.

Each design is a valid project and draws a thumbnail through the renderer; every
name a library shows has an English string; placeholders carry no dashes; and
dark text on a light plate turns off the renderer's default outline (a black
outline one thirty-second of the size, which smears dark letters).
"""

import json

from app import template_library, text_templates
from app.render_document import validate_document
from conftest import ROOT

EN = json.loads((ROOT / "frontend" / "src" / "i18n" / "en.json").read_text(encoding="utf-8"))


def _all_text_clips():
    for entry in text_templates.TEXT_TEMPLATES:
        yield entry["id"], entry["clips"]
    for template_id in template_library.BUILDERS:
        item = template_library.template(template_id)
        for timeline in item["project"]["timelines"]:
            for track in timeline["tracks"]:
                yield template_id, [c for c in track["clips"] if c.get("kind") == "text"]


def test_sixteen_designs_each_a_valid_project_with_a_thumbnail():
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)
    listed = client.get("/api/presets/texttemplates").json()
    assert len(listed) == 16 and len({entry["id"] for entry in listed}) == 16
    for entry in listed:
        validate_document(text_templates.project(entry["id"], 1920, 1080))
        assert all(clip["offset"] >= 0 and clip["duration"] > 0 for clip in entry["clips"])
        thumb = client.get(f"/api/catalogue/preview/texttemplate/{entry['id']}")
        assert thumb.status_code == 200 and thumb.content[:4] == b"\x89PNG"


def test_every_name_a_library_shows_has_an_english_string():
    keys = [entry["nameKey"] for entry in text_templates.listing()]
    for template_id in template_library.BUILDERS:
        item = template_library.template(template_id)
        keys += [item["nameKey"], *(slot["nameKey"] for slot in item["slots"])]
    missing = [key for key in keys if key not in EN]
    assert not missing, missing


def test_placeholders_carry_no_dashes():
    for owner, clips in _all_text_clips():
        for clip in clips:
            assert "\u2014" not in clip["textStyle"]["content"] and "\u2013" not in clip["textStyle"]["content"], owner


def _luminance(colour: str) -> float:
    r, g, b = (int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_dark_text_on_a_light_plate_has_no_default_outline():
    for owner, clips in _all_text_clips():
        for clip in clips:
            style = clip["textStyle"]
            if (
                style.get("plateColor")
                and style.get("plateOpacity", 0) >= 0.9
                and _luminance(style["plateColor"]) > _luminance(style["color"]) + 0.3
            ):
                assert style.get("outlineWidth") == 0, (owner, style["content"])


def test_caption_overflow_goes_above_the_busy_track_not_beneath_the_footage():
    source = (ROOT / "frontend" / "src" / "engine" / "captions.ts").read_text(encoding="utf-8")
    assert '"track.insert"' in source and '"track.add"' not in source
