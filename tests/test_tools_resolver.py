"""Finding formcut's own ffmpeg.

The resolver decides which ffmpeg every export and probe runs, so a mistake
here silently runs the wrong binary. These run on Linux, macOS and Windows, so
nothing assumes this machine's triple: names come from `tools._names`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from app import tools

POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="exercises the POSIX branch")


class WindowsOS:
    """os, except that it says it is Windows, so only the resolver's own branch changes."""

    name = "nt"

    def __getattr__(self, attribute):
        return getattr(os, attribute)


def programs(folder: Path, *names: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_text("program")
    return folder


@POSIX_ONLY
def test_an_intel_linux_machine_is_x86_64_linux_gnu(monkeypatch):
    monkeypatch.setattr(tools.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(tools.sys, "platform", "linux")
    assert tools.host_triple() == "x86_64-unknown-linux-gnu"


@POSIX_ONLY
def test_an_arm_linux_machine_is_aarch64_linux_gnu(monkeypatch):
    monkeypatch.setattr(tools.platform, "machine", lambda: "aarch64")
    monkeypatch.setattr(tools.sys, "platform", "linux")
    assert tools.host_triple() == "aarch64-unknown-linux-gnu"


@POSIX_ONLY
def test_apple_silicon_is_aarch64_apple_darwin(monkeypatch):
    monkeypatch.setattr(tools.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(tools.sys, "platform", "darwin")
    assert tools.host_triple() == "aarch64-apple-darwin"


@POSIX_ONLY
def test_an_intel_mac_is_x86_64_apple_darwin(monkeypatch):
    monkeypatch.setattr(tools.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(tools.sys, "platform", "darwin")
    assert tools.host_triple() == "x86_64-apple-darwin"


def test_windows_is_x86_64_pc_windows_msvc(monkeypatch):
    monkeypatch.setattr(tools, "os", WindowsOS())
    monkeypatch.setattr(tools.platform, "machine", lambda: "AMD64")
    monkeypatch.setattr(tools.sys, "platform", "win32")
    assert tools.host_triple() == "x86_64-pc-windows-msvc"


@POSIX_ONLY
def test_the_mac_folder_is_in_application_support(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(tools.sys, "platform", "darwin")
    assert tools.user_ffmpeg_dir() == tmp_path / "Library" / "Application Support" / "formcut" / "ffmpeg"


@POSIX_ONLY
def test_the_linux_folder_follows_xdg_data_home(monkeypatch, tmp_path):
    monkeypatch.setattr(tools.sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert tools.user_ffmpeg_dir() == tmp_path / "data" / "formcut" / "ffmpeg"


@POSIX_ONLY
def test_the_linux_folder_defaults_to_local_share(monkeypatch, tmp_path):
    monkeypatch.setattr(tools.sys, "platform", "linux")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert tools.user_ffmpeg_dir() == tmp_path / ".local" / "share" / "formcut" / "ffmpeg"


def test_the_windows_folder_is_in_local_app_data(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "os", WindowsOS())
    monkeypatch.setattr(tools.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert tools.user_ffmpeg_dir() == tmp_path / "formcut" / "ffmpeg"


@POSIX_ONLY
def test_names_are_the_plain_name_and_the_triple_name():
    assert tools._names("ffprobe") == ("ffprobe", f"ffprobe-{tools.host_triple()}")


def test_windows_names_end_in_exe(monkeypatch):
    monkeypatch.setattr(tools, "os", WindowsOS())
    plain, tripled = tools._names("ffmpeg")
    assert plain == "ffmpeg.exe" and tripled.endswith(".exe") and tripled.startswith("ffmpeg-")


def test_an_empty_folder_holds_no_ffmpeg(tmp_path):
    assert not tools._holds_ffmpeg(tmp_path)


def test_a_plainly_named_ffmpeg_counts(tmp_path):
    assert tools._holds_ffmpeg(programs(tmp_path, tools._names("ffmpeg")[0]))


def test_an_ffmpeg_named_for_this_machine_counts(tmp_path):
    assert tools._holds_ffmpeg(programs(tmp_path, tools._names("ffmpeg")[1]))


def test_an_ffmpeg_named_for_another_machine_does_not_count(tmp_path):
    assert not tools._holds_ffmpeg(programs(tmp_path, "ffmpeg-riscv64-unknown-linux-gnu"))


def test_the_named_folder_wins(monkeypatch, tmp_path):
    chosen = programs(tmp_path / "chosen", tools._names("ffmpeg")[0])
    monkeypatch.setenv("FORMCUT_FFMPEG_DIR", str(chosen))
    monkeypatch.setattr(tools, "user_ffmpeg_dir", lambda: programs(tmp_path / "person", tools._names("ffmpeg")[0]))
    assert tools.bundle_dir() == chosen


def test_a_named_folder_without_ffmpeg_is_passed_over(monkeypatch, tmp_path):
    person = programs(tmp_path / "person", tools._names("ffmpeg")[1])
    monkeypatch.setenv("FORMCUT_FFMPEG_DIR", str(tmp_path / "empty"))
    monkeypatch.setattr(tools, "user_ffmpeg_dir", lambda: person)
    assert tools.bundle_dir() == person


def test_the_per_person_folder_is_found(monkeypatch, tmp_path):
    person = programs(tmp_path / "person", tools._names("ffmpeg")[1])
    monkeypatch.delenv("FORMCUT_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(tools, "user_ffmpeg_dir", lambda: person)
    assert tools.bundle_dir() == person


def test_triple_named_programs_get_their_plain_names_beside_them(tmp_path):
    folder = programs(tmp_path, tools._names("ffmpeg")[1], tools._names("ffprobe")[1])
    tools._plain_names(folder)
    for program in ("ffmpeg", "ffprobe"):
        plain, tripled = (folder / name for name in tools._names(program))
        assert os.path.samefile(plain, tripled)


def test_a_file_already_under_the_plain_name_is_never_touched(tmp_path):
    folder = programs(tmp_path, tools._names("ffmpeg")[1])
    own = folder / tools._names("ffmpeg")[0]
    own.write_text("the person's own")
    tools._plain_names(folder)
    assert own.read_text() == "the person's own"


@POSIX_ONLY
def test_a_dangling_link_is_left_as_it_is(tmp_path):
    folder = programs(tmp_path, tools._names("ffmpeg")[1])
    plain = folder / "ffmpeg"
    plain.symlink_to("gone")
    tools._plain_names(folder)
    assert os.readlink(plain) == "gone"


def test_a_program_that_is_not_there_gets_no_name(tmp_path):
    folder = programs(tmp_path, tools._names("ffmpeg")[1])
    tools._plain_names(folder)
    assert not (folder / tools._names("ffprobe")[0]).exists()


def test_the_adopted_folder_goes_first_on_path_once(monkeypatch, tmp_path):
    folder = programs(tmp_path, tools._names("ffmpeg")[0])
    monkeypatch.setattr(tools, "bundle_dir", lambda: folder)
    monkeypatch.setenv("PATH", os.pathsep.join(["/one", "/two"]))
    tools.prefer_bundled()
    tools.prefer_bundled()
    entries = os.environ["PATH"].split(os.pathsep)
    assert entries[0] == str(folder) and entries.count(str(folder)) == 1


def test_nothing_adopted_leaves_path_alone(monkeypatch):
    monkeypatch.setattr(tools, "bundle_dir", lambda: None)
    monkeypatch.setenv("PATH", "/unchanged")
    assert tools.prefer_bundled() is None and os.environ["PATH"] == "/unchanged"


def test_windows_puts_the_dll_folder_on_path_after_the_programs(monkeypatch, tmp_path):
    folder = programs(tmp_path, "ffmpeg.exe")
    (folder / "lib-x86_64-pc-windows-msvc").mkdir()
    monkeypatch.setattr(tools, "os", WindowsOS())
    monkeypatch.setattr(tools, "bundle_dir", lambda: folder)
    monkeypatch.setenv("PATH", "/system")
    tools.prefer_bundled()
    assert os.environ["PATH"].split(os.pathsep)[:3] == [str(folder), str(folder / "lib-x86_64-pc-windows-msvc"), "/system"]


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), reason="needs permissions that bind")
def test_a_folder_that_cannot_be_given_plain_names_is_not_adopted(monkeypatch, tmp_path):
    folder = programs(tmp_path / "locked", tools._names("ffmpeg")[1])
    folder.chmod(0o555)
    monkeypatch.setattr(tools, "bundle_dir", lambda: folder)
    monkeypatch.setenv("PATH", "/system")
    try:
        assert tools.prefer_bundled() is None and os.environ["PATH"] == "/system"
    finally:
        folder.chmod(0o755)


def test_the_licence_note_says_when_nothing_is_bundled(monkeypatch):
    monkeypatch.setattr(tools, "bundle_dir", lambda: None)
    assert tools.licence_note() == {"bundled": False}


def test_the_licence_note_carries_the_record_and_the_licence_text(monkeypatch, tmp_path):
    folder = programs(tmp_path, tools._names("ffmpeg")[0], "LGPL-2.1.txt")
    (folder / "ffmpeg-licence.json").write_text(json.dumps({"licence": {"ffmpeg": "LGPL-2.1-or-later"}}))
    monkeypatch.setattr(tools, "bundle_dir", lambda: folder)
    note = tools.licence_note()
    assert note["bundled"] and note["licenceText"] and note["licence"]["ffmpeg"] == "LGPL-2.1-or-later"


def test_a_broken_record_does_not_break_the_note(monkeypatch, tmp_path):
    folder = programs(tmp_path, tools._names("ffmpeg")[0])
    (folder / "ffmpeg-licence.json").write_text("{not json")
    monkeypatch.setattr(tools, "bundle_dir", lambda: folder)
    assert tools.licence_note()["bundled"] is True
