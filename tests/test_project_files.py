"""Media linked where it is, found again when it moves, and projects kept in .fmc files (v2.2.4)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest
from app import linking, media, project_files, store
from app.main import app
from app.renderer import FrameRenderer
from fastapi.testclient import TestClient

FFMPEG = shutil.which("ffmpeg")
pytestmark = [
    pytest.mark.skipif(FFMPEG is None, reason="ffmpeg makes the clips"),
    pytest.mark.skipif(sys.platform == "win32", reason="links need developer mode on Windows; copies are used there"),
]


def _clip(folder, name, seconds=1, source="testsrc2"):
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / name
    subprocess.run(
        [
            FFMPEG,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"{source}=size=160x90:rate=30",
            "-t",
            str(seconds),
            "-pix_fmt",
            "yuv420p",
            str(out),
        ],
        check=True,
    )
    return out


def _project(media_id, label, project_id):
    clip = {"id": "c", "kind": "video", "label": label, "mediaId": media_id, "start": 0, "duration": 1, "sourceIn": 0}
    return {
        "id": project_id,
        "title": "Launch",
        "width": 160,
        "height": 90,
        "fps": 30,
        "duration": 1,
        "activeTimeline": 0,
        "timelines": [{"id": "t", "name": "t", "tracks": [{"id": "v", "name": "V", "clips": [clip]}]}],
    }


@pytest.fixture
def client():
    return TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})


def test_a_linked_file_is_read_where_it_is_and_never_copied_or_deleted(tmp_path, client):
    original = _clip(tmp_path / "Footage", "shot 01.mp4")
    item = client.post("/api/media/link", json={"paths": [str(original)]}).json()[0]
    assert item["linked"] and item["path"] == str(original.resolve()) and item["name"] == "shot 01.mp4" and ":" in item["fingerprint"]
    link = media.media_path(item["id"])
    assert link.is_symlink() and link.resolve() == original.resolve()
    assert client.get(f"/api/media/{item['id']}/file").content == original.read_bytes()
    assert client.post("/api/media/link", json={"paths": [str(original)]}).json()[0]["id"] == item["id"]  # the same file once
    assert FrameRenderer(_project(item["id"], "shot 01.mp4", "p-link")).frame(0.5).mean() > 10
    client.delete(f"/api/media/{item['id']}")
    assert original.is_file()  # the library's link went, the footage stays


def test_a_moved_file_is_missing_then_found_again(tmp_path, client):
    original = _clip(tmp_path / "Footage", "interview.mp4", seconds=2)
    item = linking.link_path(original)
    moved = tmp_path / "Archive" / "2026" / "interview.mp4"
    moved.parent.mkdir(parents=True)
    original.rename(moved)
    assert [m["id"] for m in client.get(f"/api/media/missing?ids={item['id']}").json()] == [item["id"]]
    other = _clip(tmp_path / "Other", "short.mp4", seconds=1)
    assert client.post(f"/api/media/{item['id']}/relink", json={"path": str(other)}).status_code == 409  # another length: asked first
    image = tmp_path / "still.png"
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "color=red:size=16x16", "-frames:v", "1", str(image)], check=True)
    assert client.post(f"/api/media/{item['id']}/relink", json={"path": str(image)}).status_code == 400  # another kind
    done = client.post(f"/api/media/{item['id']}/relink", json={"path": str(moved)}).json()
    assert done["path"] == str(moved.resolve()) and media.media_path(item["id"]).resolve() == moved.resolve()
    assert not linking.missing([item["id"]])


def test_searching_a_folder_finds_every_missing_file_by_name_or_fingerprint(tmp_path, client):
    first = linking.link_path(_clip(tmp_path / "Shoot", "a.mp4"))
    second = linking.link_path(_clip(tmp_path / "Shoot", "b.mp4", source="mandelbrot"))
    drive = tmp_path / "Drive" / "Project" / "Media"
    drive.mkdir(parents=True)
    (tmp_path / "Shoot" / "a.mp4").rename(drive / "a.mp4")  # moved, same name
    (tmp_path / "Shoot" / "b.mp4").rename(drive / "renamed take.mp4")  # moved and renamed
    found = client.post("/api/media/relink-search", json={"folder": str(tmp_path / "Drive"), "ids": [first["id"], second["id"]]}).json()
    assert sorted(r["id"] for r in found["relinked"]) == sorted([first["id"], second["id"]]) and not found["missing"]
    assert media.media_path(second["id"]).resolve() == (drive / "renamed take.mp4").resolve()


def test_a_project_file_saves_follows_saves_and_opens_elsewhere_with_its_media(tmp_path, client):
    folder = tmp_path / "Client"
    footage = _clip(folder / "Footage", "hero.mp4")
    item = linking.link_path(footage)
    project = store.save_project(_project(item["id"], "hero.mp4", "p-file"))
    where = folder / "Launch"
    saved = client.post("/api/project-files/save", json={"projectId": project["id"], "path": str(where)}).json()["path"]
    document = json.loads((folder / "Launch.fmc").read_text())
    assert saved.endswith("Launch.fmc") and document["format"] == "formcut-project-file" and document["version"] == 1
    entry = document["media"][item["id"]]
    assert (
        entry["path"] == str(footage.resolve()) and entry["relative"] == "Footage/hero.mp4" and entry["fingerprint"] == item["fingerprint"]
    )
    # the file follows a save of the project
    store.save_project({**project, "title": "Launch v2"})
    assert json.loads((folder / "Launch.fmc").read_text())["project"]["title"] == "Launch v2"
    # the whole folder handed over: moved, and this library no longer knowing the media
    moved = tmp_path / "Elsewhere"
    shutil.move(str(folder), str(moved))
    media.delete_media(item["id"])
    opened = client.post("/api/project-files/open", json={"path": str(moved / "Launch.fmc")}).json()
    assert opened["project"]["id"] == "p-file" and opened["linked"] == [item["id"]] and not opened["missing"]
    assert media.media_path(item["id"]).resolve() == (moved / "Footage" / "hero.mp4").resolve()
    # and with the footage gone: missing, still named, ready to relink
    (moved / "Footage" / "hero.mp4").rename(tmp_path / "hero.mp4")
    media.delete_media(item["id"])
    opened = client.post("/api/project-files/open", json={"path": str(moved / "Launch.fmc")}).json()
    assert [m["name"] for m in opened["missing"]] == ["hero.mp4"] and linking.missing([item["id"]])[0]["name"] == "hero.mp4"
    assert client.post(f"/api/media/{item['id']}/relink", json={"path": str(tmp_path / "hero.mp4")}).status_code == 200
    assert project_files.file_of("p-file") == moved / "Launch.fmc"
    assert client.post("/api/project-files/open", json={"path": str(tmp_path / "hero.mp4")}).status_code == 400


def test_the_interface_offers_project_files_linking_and_the_missing_media_dialog():
    from pathlib import Path

    ui = Path(__file__).resolve().parents[1] / "frontend" / "src" / "ui"
    menu, bar, pane, dialog = (
        (ui / name).read_text(encoding="utf-8") for name in ("file-menu.ts", "titlebar.ts", "media-pane.ts", "missing-media.ts")
    )
    assert '["open-file", "file.openFile"]' in menu and '["save-as", "file.saveAs"]' in menu
    assert "/api/project-files/open" in bar and "/api/project-files/save" in bar and "showMissingMedia(" in bar
    assert "/api/media/link" in pane and "/api/system/dialogs" in pane and "showMissingMedia(" in pane
    assert "/api/media/relink-search" in dialog and "/relink`" in dialog and "missing.useAnyway" in dialog
