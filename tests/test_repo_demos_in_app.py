"""The three repository demos open inside the app, and every file they ship is credited.

scripts/extract_demo_media.py writes each demo's media to frontend/public/demos/<id>/ with a
manifest; POST /api/demo/<id> seeds those files into the library (once) and returns them keyed by
the demo's media id, which frontend/src/demos/index.ts swaps into the film built by the demo's code.
"""

import json

from conftest import ROOT

DEMOS = ROOT / "frontend" / "public" / "demos"


def _manifest(demo_id):
    return json.loads((DEMOS / demo_id / "manifest.json").read_text(encoding="utf-8"))["items"]


def test_each_demo_ships_its_manifest_files_and_poster():
    from app.demo import REPO_DEMOS

    assert REPO_DEMOS == ("edit", "grade", "deliver")
    for demo_id in REPO_DEMOS:
        items = _manifest(demo_id)
        assert items, demo_id
        for item in items:
            assert (DEMOS / demo_id / item["file"]).stat().st_size > 0
        assert (DEMOS / demo_id / "poster.jpg").is_file()


def test_the_app_opens_every_demo_from_start_and_help():
    index = (ROOT / "frontend" / "src" / "demos" / "index.ts").read_text(encoding="utf-8")
    for demo_id in ("edit", "grade", "deliver"):
        assert f'id: "{demo_id}"' in index
    main = (ROOT / "src-tauri" / "src" / "main.rs").read_text(encoding="utf-8")
    for demo_id in ("edit", "grade", "deliver"):
        assert f'openDemo(\\"{demo_id}\\")' in main


def test_notice_credits_every_shipped_demo_file():
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    section = notice.split("Demo films\n----------", 1)
    assert len(section) == 2, "NOTICE has no Demo films section"
    for demo_id in ("edit", "grade", "deliver"):
        for item in _manifest(demo_id):
            entry = next((e for e in section[1].split("\n- ") if e.lstrip("- ").startswith(f"demos/{demo_id}/{item['file']}:")), "")
            assert entry, f"{demo_id}/{item['file']} has no credit in NOTICE"
            assert " by " in entry and "https://" in entry, f"{demo_id}/{item['file']} credit is incomplete"


def test_seeding_a_demo_returns_every_media_id(monkeypatch):
    from app import demo
    from app.main import app
    from fastapi.testclient import TestClient

    calls = []
    monkeypatch.setattr(
        demo, "ingest_path", lambda path, name, extra=None: calls.append(name) or {"id": name, "name": name, **(extra or {})}
    )
    monkeypatch.setattr(demo, "_read", lambda: [])
    client = TestClient(app)
    headers = {"x-formcut-local": "1"}
    first = client.post("/api/demo/grade", headers=headers)
    assert first.status_code == 200
    assert set(first.json()["media"]) == {item["id"] for item in _manifest("grade")}
    assert client.post("/api/demo/nothing", headers=headers).status_code == 404
