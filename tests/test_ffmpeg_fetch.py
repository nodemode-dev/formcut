"""Fetching formcut's own ffmpeg.

The fetch runs unattended on a person's machine, so what matters is what it
refuses: a changed file, a missing one, a path that climbs out of its folder,
and any run at all when the person already has an ffmpeg.
"""

from __future__ import annotations

import hashlib
import http.server
import io
import json
import os
import tarfile
import threading
from pathlib import Path

import pytest
from app import ffmpeg_fetch, tools

TRIPLE = tools.host_triple()
FILES = {
    f"ffmpeg-{TRIPLE}": b"the ffmpeg program",
    f"ffprobe-{TRIPLE}": b"the ffprobe program",
    f"lib-{TRIPLE}/libavcodec.so.61": b"a codec library",
}


def archive(folder: Path, files: dict[str, bytes], top: str = "ffmpeg-lgpl") -> Path:
    path = folder / "bundle.tar.gz"
    with tarfile.open(path, "w:gz") as bundle:
        for name, data in files.items():
            member = tarfile.TarInfo(f"{top}/{name}" if top else name)
            member.size, member.mode = len(data), 0o755
            bundle.addfile(member, io.BytesIO(data))
    return path


def recorded(files: dict[str, bytes]) -> list[dict]:
    return [{"path": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)} for name, data in files.items()]


def test_a_verified_archive_is_installed_whole(tmp_path):
    folder = tmp_path / "ffmpeg"
    assert ffmpeg_fetch.install(archive(tmp_path, FILES), recorded(FILES), folder) == 3
    assert all((folder / name).read_bytes() == data for name, data in FILES.items())


@pytest.mark.skipif(os.name == "nt", reason="POSIX permission bits")
def test_the_programs_stay_executable(tmp_path):
    folder = tmp_path / "ffmpeg"
    ffmpeg_fetch.install(archive(tmp_path, FILES), recorded(FILES), folder)
    assert os.stat(folder / f"ffmpeg-{TRIPLE}").st_mode & 0o100


def test_one_changed_file_installs_nothing(tmp_path):
    folder = tmp_path / "ffmpeg"
    changed = {**FILES, f"ffprobe-{TRIPLE}": b"something else"}
    with pytest.raises(ValueError, match="does not match"):
        ffmpeg_fetch.install(archive(tmp_path, changed), recorded(FILES), folder)
    assert not folder.exists()


def test_a_missing_file_installs_nothing(tmp_path):
    folder = tmp_path / "ffmpeg"
    short = {name: data for name, data in FILES.items() if "libavcodec" not in name}
    with pytest.raises(ValueError, match="has no"):
        ffmpeg_fetch.install(archive(tmp_path, short), recorded(FILES), folder)
    assert not folder.exists()


def test_an_archive_without_the_program_is_refused(tmp_path):
    with pytest.raises(ValueError, match="has no"):
        ffmpeg_fetch.install(archive(tmp_path, {"README.md": b"notes"}), recorded(FILES), tmp_path / "ffmpeg")


def test_a_path_that_climbs_out_of_the_archive_is_refused(tmp_path):
    with pytest.raises(tarfile.TarError):
        ffmpeg_fetch.install(archive(tmp_path, {**FILES, "../../escaped": b"x"}, top=""), recorded(FILES), tmp_path / "ffmpeg")
    assert not (tmp_path.parent / "escaped").exists()


def test_the_licence_text_comes_along(tmp_path):
    folder = tmp_path / "ffmpeg"
    ffmpeg_fetch.install(archive(tmp_path, {**FILES, "LGPL-2.1.txt": b"licence"}), recorded(FILES), folder)
    assert (folder / "LGPL-2.1.txt").read_bytes() == b"licence"


def test_files_at_the_top_of_the_archive_are_found(tmp_path):
    folder = tmp_path / "ffmpeg"
    assert ffmpeg_fetch.install(archive(tmp_path, FILES, top=""), recorded(FILES), folder) == 3


def test_the_source_names_the_version_and_this_machine(monkeypatch):
    monkeypatch.delenv("FORMCUT_FFMPEG_RELEASE", raising=False)
    urls = ffmpeg_fetch.source({"source": {"ffmpeg": {"version": "7.1.5"}}}, TRIPLE)
    assert urls == [f"{base}/ffmpeg-7.1.5/ffmpeg-lgpl-7.1.5-{TRIPLE}.tar.gz" for base in ffmpeg_fetch.RELEASES]


def test_the_new_binaries_address_comes_first_and_the_old_one_second(monkeypatch):
    monkeypatch.delenv("FORMCUT_FFMPEG_RELEASE", raising=False)
    urls = ffmpeg_fetch.source({"release": "7.1.5-2"}, TRIPLE)
    assert [url.split("/releases/")[0] for url in urls] == [
        "https://github.com/nodemode-dev/formai-binaries",
        "https://github.com/nodemode-dev/formcut-binaries",
    ]


def test_a_mirror_can_be_named(monkeypatch):
    monkeypatch.setenv("FORMCUT_FFMPEG_RELEASE", "https://mirror.example/ffmpeg/")
    urls = ffmpeg_fetch.source({"source": {"ffmpeg": {"version": "7.1.5"}}}, TRIPLE)
    assert urls == [f"https://mirror.example/ffmpeg/ffmpeg-lgpl-7.1.5-{TRIPLE}.tar.gz"]


def test_the_record_formcut_carries_pins_every_linux_file():
    files = ffmpeg_fetch.pins(ffmpeg_fetch.record(), "x86_64-unknown-linux-gnu")
    assert len(files) == 12 and all(len(entry["sha256"]) == 64 for entry in files)
    names = {Path(entry["path"]).name for entry in files}
    assert {"libva.so.2", "libva-drm.so.2", "libdrm.so.2"} <= names


@pytest.mark.parametrize("triple", ["aarch64-apple-darwin", "x86_64-apple-darwin", "x86_64-unknown-linux-gnu", "x86_64-pc-windows-msvc"])
def test_every_released_target_is_pinned(triple):
    assert ffmpeg_fetch.pins(ffmpeg_fetch.record(), triple)


def test_nothing_is_fetched_when_ffmpeg_is_on_path(monkeypatch):
    monkeypatch.setattr(tools, "bundle_dir", lambda: None)
    monkeypatch.setattr(ffmpeg_fetch.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    assert ffmpeg_fetch.auto_fetch() is None


def test_nothing_is_fetched_when_a_build_is_placed(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "bundle_dir", lambda: tmp_path)
    monkeypatch.setattr(ffmpeg_fetch.shutil, "which", lambda name: None)
    assert ffmpeg_fetch.needed() is False


def test_the_fetch_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(ffmpeg_fetch, "needed", lambda: True)
    monkeypatch.setenv("FORMCUT_FFMPEG_AUTO", "0")
    assert ffmpeg_fetch.auto_fetch() is None


def test_a_full_fetch_installs_and_adopts(monkeypatch, tmp_path):
    source = archive(tmp_path, FILES)
    folder = tmp_path / "person" / "ffmpeg"
    record = {"source": {"ffmpeg": {"version": "7.1.5"}}, "targets": {TRIPLE: {"files": recorded(FILES)}}}
    monkeypatch.setattr(ffmpeg_fetch, "record", lambda: record)
    monkeypatch.setattr(ffmpeg_fetch, "_download", lambda url, path, report, cancelled: path.write_bytes(source.read_bytes()))
    monkeypatch.setattr(tools, "user_ffmpeg_dir", lambda: folder)
    monkeypatch.setattr(tools, "prefer_bundled", lambda: folder)
    result = ffmpeg_fetch.fetch(lambda fraction: None, lambda: False)
    assert result["files"] == 3 and result["adopted"] == str(folder)
    assert json.loads((folder / "ffmpeg-licence.json").read_text())["targets"][TRIPLE]


def test_a_fetch_without_the_record_says_so(monkeypatch):
    monkeypatch.setattr(ffmpeg_fetch, "record", lambda: None)
    with pytest.raises(ValueError, match="record is missing"):
        ffmpeg_fetch.fetch(lambda fraction: None, lambda: False)


def test_a_machine_with_no_recorded_build_says_so(monkeypatch):
    monkeypatch.setattr(ffmpeg_fetch, "record", lambda: {"targets": {}})
    with pytest.raises(ValueError, match="no ffmpeg build is recorded"):
        ffmpeg_fetch.fetch(lambda fraction: None, lambda: False)


def test_the_release_name_tags_the_address_when_the_record_has_one():
    data = {"release": "7.1.5-2", "source": {"ffmpeg": {"version": "7.1.5"}}}
    urls = ffmpeg_fetch.source(data, TRIPLE)
    assert urls == [f"{base}/ffmpeg-7.1.5-2/ffmpeg-lgpl-7.1.5-2-{TRIPLE}.tar.gz" for base in ffmpeg_fetch.RELEASES]
    assert ffmpeg_fetch.release(ffmpeg_fetch.record()) == "7.1.5-2"


def _own_download(monkeypatch, tmp_path, installed: str | None, carried: str = "7.1.5-2") -> Path:
    folder = tmp_path / "own"
    folder.mkdir()
    if installed is not None:
        (folder / "ffmpeg-licence.json").write_text(json.dumps({"release": installed}), encoding="utf-8")
    monkeypatch.setattr(tools, "user_ffmpeg_dir", lambda: folder)
    monkeypatch.setattr(tools, "bundle_dir", lambda: folder)
    monkeypatch.setattr(ffmpeg_fetch.shutil, "which", lambda name: None)
    monkeypatch.setattr(ffmpeg_fetch, "record", lambda: {"release": carried, "targets": {TRIPLE: {"files": recorded(FILES)}}})
    return folder


def test_formcut_refreshes_its_own_download_from_an_older_release(monkeypatch, tmp_path):
    _own_download(monkeypatch, tmp_path, installed="7.1.5")
    assert ffmpeg_fetch.outdated() is True and ffmpeg_fetch.needed() is True


def test_the_same_release_is_not_fetched_again(monkeypatch, tmp_path):
    _own_download(monkeypatch, tmp_path, installed="7.1.5-2")
    assert ffmpeg_fetch.needed() is False


def test_an_ffmpeg_placed_by_hand_is_never_refreshed(monkeypatch, tmp_path):
    _own_download(monkeypatch, tmp_path, installed=None)
    assert ffmpeg_fetch.needed() is False


def test_an_ffmpeg_formcut_is_pointed_at_is_never_refreshed(monkeypatch, tmp_path):
    _own_download(monkeypatch, tmp_path, installed="7.1.5")
    monkeypatch.setattr(tools, "bundle_dir", lambda: tmp_path / "chosen")
    assert ffmpeg_fetch.needed() is False


def test_a_refresh_brings_the_new_licence_documents(tmp_path):
    folder = tmp_path / "ffmpeg"
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    ffmpeg_fetch.install(archive(tmp_path / "a", {**FILES, "THIRD-PARTY-NOTICES.txt": b"old"}), recorded(FILES), folder)
    ffmpeg_fetch.install(archive(tmp_path / "b", {**FILES, "THIRD-PARTY-NOTICES.txt": b"new, with libva"}), recorded(FILES), folder)
    assert (folder / "THIRD-PARTY-NOTICES.txt").read_bytes() == b"new, with libva"


@pytest.fixture
def releases(monkeypatch, tmp_path):
    """Two release addresses on a loopback server: files placed under served/new and served/old answer, others 404."""
    served = tmp_path / "served"
    served.mkdir()
    asked = []

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(served), **kwargs)

        def log_message(self, *args):
            asked.append(self.path)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setenv("no_proxy", "127.0.0.1")
    monkeypatch.delenv("FORMCUT_FFMPEG_RELEASE", raising=False)
    monkeypatch.setattr(ffmpeg_fetch, "RELEASES", (f"{base}/new", f"{base}/old"))
    record = {"release": "7.1.5-2", "targets": {TRIPLE: {"files": recorded(FILES)}}}
    monkeypatch.setattr(ffmpeg_fetch, "record", lambda: record)
    folder = tmp_path / "person" / "ffmpeg"
    monkeypatch.setattr(tools, "user_ffmpeg_dir", lambda: folder)
    monkeypatch.setattr(tools, "prefer_bundled", lambda: folder)

    def publish(where: str, files: dict[str, bytes]) -> None:
        release = served / where / "ffmpeg-7.1.5-2"
        release.mkdir(parents=True)
        archive(release, files).rename(release / f"ffmpeg-lgpl-7.1.5-2-{TRIPLE}.tar.gz")

    yield publish, folder, base, asked
    server.shutdown()
    server.server_close()


def _fetch() -> dict:
    return ffmpeg_fetch.fetch(lambda fraction: None, lambda: False)


def test_the_old_address_is_used_while_the_new_one_answers_404(releases):
    publish, folder, base, _ = releases
    publish("old", FILES)
    result = _fetch()
    assert result["source"].startswith(f"{base}/old/") and result["files"] == 3
    assert all((folder / name).read_bytes() == data for name, data in FILES.items())


def test_the_new_address_is_used_when_it_answers(releases):
    publish, _, base, asked = releases
    publish("new", FILES)
    assert _fetch()["source"].startswith(f"{base}/new/")
    assert not [path for path in asked if path.startswith("/old/")]


def test_a_changed_file_from_the_old_address_is_still_refused(releases):
    publish, folder, _, _ = releases
    publish("old", {**FILES, f"ffmpeg-{TRIPLE}": b"something else"})
    with pytest.raises(ValueError, match="does not match"):
        _fetch()
    assert not folder.exists()


def test_neither_address_answering_names_both(releases):
    _, folder, base, _ = releases
    with pytest.raises(OSError, match="could not be downloaded") as raised:
        _fetch()
    assert f"{base}/new/" in str(raised.value) and f"{base}/old/" in str(raised.value)
    assert not folder.exists()


def test_a_named_mirror_stays_the_only_source(releases, monkeypatch):
    publish, _, base, asked = releases
    publish("old", FILES)
    monkeypatch.setenv("FORMCUT_FFMPEG_RELEASE", f"{base}/mirror")
    with pytest.raises(OSError, match="could not be downloaded"):
        _fetch()
    assert asked and all(path.startswith("/mirror/") for path in asked)


def test_a_cancel_is_not_taken_for_a_failed_address(monkeypatch, tmp_path):
    tried = []

    def cancelled(url, path, report, cancelled):
        tried.append(url)
        raise InterruptedError("Cancelled")

    monkeypatch.setattr(ffmpeg_fetch, "_download", cancelled)
    with pytest.raises(InterruptedError):
        ffmpeg_fetch._download_first(["https://first", "https://second"], tmp_path / "a", lambda fraction: None, lambda: True)
    assert tried == ["https://first"]
