"""formcut's own templates: each is a valid template, fills through the same route
as a person's, and renders with real media in its slots."""

import shutil

import pytest
from app import catalogue, template_library, templates
from app.render_document import validate_document
from conftest import ROOT

IDS = list(template_library.BUILDERS)


def _every_clip(item):
    for timeline in item["project"]["timelines"]:
        for track in timeline["tracks"]:
            yield from track["clips"]


def test_there_are_twelve_and_each_is_a_valid_template():
    assert len(IDS) == 12
    for template_id in IDS:
        item = template_library.template(template_id)
        templates.validate_template(item)
        assert template_id.isalnum() and item["bundled"] and item["nameKey"] == f"tpl.{template_id}"
        assert all(slot["kind"] in ("video", "image") and slot["nameKey"].startswith("tpl.slot.") for slot in item["slots"])


def test_they_use_only_transitions_and_effects_formcut_has():
    known = catalogue.catalogue()
    transitions = set(known["transitions"])
    effects = {entry["id"] for entry in known["video"]}
    for template_id in IDS:
        for clip in _every_clip(template_library.template(template_id)):
            if "transitionIn" in clip:
                assert clip["transitionIn"]["type"] in transitions, (template_id, clip["transitionIn"])
            for effect in clip.get("effects", []):
                assert effect["id"] in effects, (template_id, effect)


def test_their_words_hold_no_dashes():
    for template_id in IDS:
        for clip in _every_clip(template_library.template(template_id)):
            content = clip.get("textStyle", {}).get("content", "")
            assert "\u2014" not in content and "\u2013" not in content


def test_they_come_first_and_cannot_be_deleted():
    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app, headers={"x-formcut-local": "1"})
    listed = client.get("/api/templates").json()
    assert [entry["id"] for entry in listed[:12]] == IDS and all(entry["bundled"] for entry in listed[:12])
    assert client.delete(f"/api/templates/{IDS[0]}").status_code == 403


@pytest.mark.skipif(not shutil.which("ffprobe"), reason="importing media probes it")
@pytest.mark.parametrize("template_id", IDS)
def test_each_fills_with_real_media_and_renders(template_id, tmp_path):
    from app import media
    from app.main import app
    from app.renderer import FrameRenderer
    from fastapi.testclient import TestClient

    shutil.copy(ROOT / "examples" / "demo" / "input-clip-example.mp4", tmp_path / "v.mp4")
    shutil.copy(ROOT / "examples" / "demo" / "effect-example-image.jpg", tmp_path / "p.jpg")
    video = media.ingest_path(tmp_path / "v.mp4", "v.mp4")
    photo = media.ingest_path(tmp_path / "p.jpg", "p.jpg")
    client = TestClient(app, headers={"x-formcut-local": "1"})
    item = client.get(f"/api/templates/{template_id}").json()
    bindings = {slot["id"]: (video if slot["kind"] == "video" else photo)["id"] for slot in item["slots"]}
    response = client.post(f"/api/templates/{template_id}/fill", json={"bindings": bindings, "title": "t", "fit": True})
    assert response.status_code == 200, response.text
    project = validate_document(response.json())
    renderer = FrameRenderer(project, 320)
    for moment in (0.2, 0.5, 0.85):
        frame = renderer.frame(project["duration"] * moment)
        assert frame.shape[0] > 0 and frame[..., :3].max() > 0, "something is drawn"
