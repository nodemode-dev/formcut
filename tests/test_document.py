"""The project document: what is accepted, and what is refused with a reason."""

from __future__ import annotations

import pytest
from conftest import make_project, text_clip


def valid(document):
    from app.render_document import validate_document

    return validate_document(document)


def test_a_plain_project_validates(project):
    assert valid(project)["width"] == 320


def test_duplicate_clip_ids_are_refused():
    document = make_project(clips=[text_clip(clip_id="same"), text_clip(clip_id="same", start=2)])
    with pytest.raises(ValueError, match="unique"):
        valid(document)


@pytest.mark.parametrize("width", [0, 8, 10000])
def test_an_impossible_frame_size_is_refused(width):
    with pytest.raises(ValueError):
        valid(make_project(width=width))


def test_a_clip_that_is_not_an_object_is_refused():
    document = make_project()
    document["timelines"][0]["tracks"][0]["clips"] = ["not a clip"]
    with pytest.raises(ValueError):
        valid(document)


def test_an_unknown_mask_shape_is_refused():
    with pytest.raises(ValueError):
        valid(make_project(clips=[text_clip(mask={"shape": "dodecahedron", "x": 0, "y": 0, "w": 50, "h": 50, "feather": 0})]))


def test_an_unknown_effect_is_refused():
    with pytest.raises(ValueError):
        valid(make_project(clips=[text_clip(effects=[{"id": "not-an-effect", "amount": 1}])]))


def test_stabilise_settings_are_kept():
    document = valid(make_project(clips=[text_clip(stabilise={"smoothing": 0.6, "crop": 0.06})]))
    assert document["timelines"][0]["tracks"][0]["clips"][0]["stabilise"]["smoothing"] == pytest.approx(0.6)


def test_a_flattened_project_lists_every_clip():
    from app.render_document import flatten

    document = valid(make_project(clips=[text_clip(clip_id="a"), text_clip(clip_id="b", start=4)]))
    assert {clip["id"] for clip in flatten(document)} == {"a", "b"}
