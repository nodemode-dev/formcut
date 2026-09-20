"""The HTTP surface and the automation contract.

These pin the shapes callers depend on. A renamed field breaks every caller and
nothing else in this suite would notice.
"""

from __future__ import annotations

import pytest
from conftest import make_project

pytest.importorskip("fastapi")


@pytest.fixture(scope="module")
def client():
    from app.main import app
    from fastapi.testclient import TestClient

    return TestClient(app)


LOCAL = {"x-formcut-local": "1"}


def test_the_engine_reports_its_version(client):
    body = client.get("/api/diagnostics").json()
    assert body["version"]


def test_every_route_is_mounted_once():
    import collections

    from app.main import app

    seen = [f"{method}:{route.path}" for route in app.routes for method in getattr(route, "methods", {"GET"})]
    repeated = [path for path, count in collections.Counter(seen).items() if count > 1]
    assert not repeated, f"mounted more than once: {repeated}"


def test_the_catalogue_lists_effects_and_transitions(client):
    body = client.get("/api/catalogue").json()
    assert body["video"] and body["audio"] and body["transitions"]


def test_a_project_can_be_made_read_renamed_and_removed(client):
    made = client.post("/api/projects", json={"title": "Round trip", "document": make_project()}, headers=LOCAL)
    assert made.status_code == 201
    project_id = made.json()["id"]
    assert client.get(f"/api/projects/{project_id}").json()["title"] == "Round trip"
    renamed = client.patch(f"/api/projects/{project_id}", json={"title": "Renamed"}, headers=LOCAL)
    assert renamed.status_code == 200 and renamed.json()["title"] == "Renamed"
    assert client.delete(f"/api/projects/{project_id}", headers=LOCAL).status_code in (200, 204)


def test_a_project_cannot_be_renamed_to_nothing(client):
    made = client.post("/api/projects", json={"title": "Keep", "document": make_project()}, headers=LOCAL)
    project_id = made.json()["id"]
    assert client.patch(f"/api/projects/{project_id}", json={"title": "  "}, headers=LOCAL).status_code == 422


def test_an_unknown_project_is_not_found(client):
    assert client.get("/api/projects/does-not-exist").status_code == 404


def test_a_bad_document_is_refused_with_a_reason(client):
    broken = make_project()
    broken["width"] = 0
    reply = client.post("/api/render/sessions", json={"project": broken}, headers=LOCAL)
    assert reply.status_code == 422
    assert reply.json().get("detail")


def test_the_h264_addon_says_why_it_is_not_installed(client):
    body = client.get("/api/addons/h264").json()
    assert "installed" in body
    if not body["installed"]:
        assert body["why"], "an absent add-on must explain itself"


def test_models_report_whether_they_are_ready(client):
    listed = client.get("/api/models").json()
    assert listed and all("ready" in entry and "license" in entry for entry in listed)


def test_every_model_download_url_is_https(client):
    from app.model_manager import MODELS

    for name, spec in MODELS.items():
        for file, url in spec["files"].items():
            assert url.startswith("https://"), f"{name}/{file} is not fetched over https"


def test_the_automation_surface_lists_its_own_verbs():
    from app.automation import dispatch

    listed = dispatch("capabilities", {})
    assert {"clip.add", "clip.update", "clips.split"} <= set(listed["edit_commands"])
    assert {"mask", "colour", "cutout", "stabilise", "smoothSlow"} <= set(listed["clip_properties"])


def test_an_unknown_rpc_method_is_refused():
    from app.automation import dispatch

    with pytest.raises((ValueError, KeyError, LookupError)):
        dispatch("not.a.method", {})


def test_locales_are_offered_with_names(client):
    listed = client.get("/api/locales").json().get("locales", [])
    assert all(entry.get("code") for entry in listed)
