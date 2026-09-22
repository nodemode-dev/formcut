"""Fetching formcut's own ffmpeg.

The fetch runs unattended on a person's machine, so what matters is what it
refuses: a changed file, a missing one, a path that climbs out of its folder,
and any run at all when the person already has an ffmpeg.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
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
    url = ffmpeg_fetch.source({"source": {"ffmpeg": {"version": "7.1.5"}}}, TRIPLE)
    assert url == f"{ffmpeg_fetch.RELEASE}/ffmpeg-7.1.5/ffmpeg-lgpl-7.1.5-{TRIPLE}.tar.gz"


def test_a_mirror_can_be_named(monkeypatch):
    monkeypatch.setenv("FORMCUT_FFMPEG_RELEASE", "https://mirror.example/ffmpeg/")
    url = ffmpeg_fetch.source({"source": {"ffmpeg": {"version": "7.1.5"}}}, TRIPLE)
    assert url == f"https://mirror.example/ffmpeg/ffmpeg-lgpl-7.1.5-{TRIPLE}.tar.gz"


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
    url = ffmpeg_fetch.source(data, TRIPLE)
    assert url == f"{ffmpeg_fetch.RELEASE}/ffmpeg-7.1.5-2/ffmpeg-lgpl-7.1.5-2-{TRIPLE}.tar.gz"
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
