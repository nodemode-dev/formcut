"""The media library survives losing media.json (v2.2.2). The owner deleted it by accident and every clip stopped
decoding, its media unknown to the engine though every file was still there. Now the index is written whole and
moved into place, the version before kept as media.json.bak, each item's record kept in media-records/; and it is
rebuilt from those, and from the files themselves, when it is missing or unreadable, while any media file it does
not know is taken back into it (when a clip asks for it, and at start)."""

from __future__ import annotations

import shutil
import subprocess

import pytest
from app import media, store
from app.renderer import FrameRenderer

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg makes the clips")


def _clip_file(tmp_path, name="in.mp4", colour="testsrc2"):
    out = tmp_path / name
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"{colour}=size=160x90:rate=30", "-t", "1", "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )
    return out


def _project(media_id, label):
    clip = {"id": "c", "kind": "video", "label": label, "mediaId": media_id, "start": 0, "duration": 1, "sourceIn": 0}
    return {
        "id": f"p-{media_id[:6]}",
        "title": "p",
        "width": 160,
        "height": 90,
        "fps": 30,
        "duration": 1,
        "activeTimeline": 0,
        "timelines": [{"id": "t", "name": "t", "tracks": [{"id": "v", "name": "V", "clips": [clip]}]}],
    }


@pytest.fixture
def library(tmp_path, monkeypatch):
    data = tmp_path / "data"
    for name, value in (
        ("MEDIA_DIR", data / "media"),
        ("THUMB_DIR", data / "thumbs"),
        ("INDEX_FILE", data / "media.json"),
        ("BACKUP_FILE", data / "media.json.bak"),
        ("RECORDS_DIR", data / "media-records"),
    ):
        monkeypatch.setattr(media, name, value)
    monkeypatch.setattr(media, "_index_cache", None)
    monkeypatch.setattr(media, "_record_texts", {})
    monkeypatch.setattr(media, "DATA_DIR", data)
    monkeypatch.setattr(store, "PROJECTS_FILE", data / "projects.json")
    monkeypatch.setattr(store, "RECORDS_DIR", data / "project-records")
    from app import renderer

    monkeypatch.setattr(renderer, "MEDIA_DIR", data / "media")
    return tmp_path


def test_a_deleted_index_comes_back_whole_and_the_clip_plays(library):
    item = media.ingest_path(_clip_file(library), "my-clip.mp4")
    project = _project(item["id"], "my-clip.mp4")
    drawn = FrameRenderer(project).frame(0.5)
    media.INDEX_FILE.unlink()
    assert [(i["id"], i["name"]) for i in media.list_media()] == [(item["id"], "my-clip.mp4")]
    assert (FrameRenderer(project).frame(0.5) == drawn).all()


def test_with_only_the_files_left_the_library_is_rebuilt_and_named_from_the_projects(library):
    used = media.ingest_path(_clip_file(library, "a.mp4"), "holiday.mp4")
    loose = media.ingest_path(_clip_file(library, "b.mp4", "mandelbrot"), "unused.mp4")
    store.save_project(_project(used["id"], "holiday.mp4"))
    media.INDEX_FILE.unlink()
    media.BACKUP_FILE.unlink()
    shutil.rmtree(media.RECORDS_DIR)
    rebuilt = {i["id"]: i for i in media.list_media()}
    assert rebuilt[used["id"]]["name"] == "holiday.mp4" and rebuilt[used["id"]]["kind"] == "video" and rebuilt[used["id"]]["recovered"]
    assert rebuilt[loose["id"]]["name"].startswith("Recovered video ")
    assert abs(rebuilt[used["id"]]["duration"] - 1.0) < 0.1


def test_an_index_that_forgot_its_media_takes_them_back(library):
    """The owner's state: an index that exists again but without the entries its files had."""
    item = media.ingest_path(_clip_file(library), "my-clip.mp4")
    media._write([])
    assert media._find(item["id"])["name"] == "my-clip.mp4"  # a clip asking for it brings it back
    media._write([])
    assert media.recover_library() == {"recovered": 1, "items": 1}


def test_a_corrupt_index_is_rebuilt_and_writes_leave_a_backup(library):
    item = media.ingest_path(_clip_file(library), "my-clip.mp4")
    media.ingest_path(_clip_file(library, "b.mp4"), "second.mp4")
    assert item["id"] in media.BACKUP_FILE.read_text()  # the version before the last write
    media.INDEX_FILE.write_text("{ half written")
    assert sorted(i["name"] for i in media.list_media()) == ["my-clip.mp4", "second.mp4"]
    assert not list(media.DATA_DIR.glob(".media-*.json"))  # no temporary left behind


def test_deleted_media_does_not_come_back(library):
    kept = media.ingest_path(_clip_file(library, "a.mp4"), "kept.mp4")
    gone = media.ingest_path(_clip_file(library, "b.mp4"), "gone.mp4")
    media.delete_media(gone["id"])
    assert not (media.RECORDS_DIR / f"{gone['id']}.json").exists()
    media.INDEX_FILE.unlink()
    assert [i["id"] for i in media.list_media()] == [kept["id"]]


def test_recovery_never_deletes_a_file(library):
    """2.2.2 to 2.2.5 dropped formcut's own demo copies once their originals were back, deleting their files, and the
    open project that used a copy lost it. Recovery keeps every file now; a duplicate is the person's to delete."""
    original = media.ingest_path(_clip_file(library, "demo.mp4"), "input-clip-example.mp4", extra={"source": "demo"})
    store.save_project(_project(original["id"], "input-clip-example.mp4"))
    media.INDEX_FILE.unlink()
    media.BACKUP_FILE.unlink()
    shutil.rmtree(media.RECORDS_DIR)
    media._write([])
    shutil.copyfile(next(media.MEDIA_DIR.glob(f"{original['id']}.*")), library / "again.mp4")
    copy = media.ingest_path(library / "again.mp4", "input-clip-example.mp4", extra={"source": "demo"})
    media.recover_library()
    ids = [i["id"] for i in media.list_media()]
    assert original["id"] in ids and copy["id"] in ids and media.media_path(copy["id"]) is not None
