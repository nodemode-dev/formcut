"""ffmpeg inside the macOS and Windows installers.

The release stages formcut's verified LGPL build as a Tauri resource under plain
program names. These check that an installed engine finds it where each
platform's installer puts it, that adopting it writes nothing, and that the
workflow and the bundle config agree on the folder.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from app import tools
from conftest import ROOT


def installed(monkeypatch, tmp_path: Path, engine: Path, ffmpeg_folder: Path) -> Path:
    engine.parent.mkdir(parents=True, exist_ok=True)
    engine.write_text("engine")
    ffmpeg_folder.mkdir(parents=True, exist_ok=True)
    (ffmpeg_folder / tools._names("ffmpeg")[0]).write_text("program")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(engine))
    monkeypatch.delenv("FORMCUT_FFMPEG_DIR", raising=False)
    monkeypatch.setattr(tools, "user_ffmpeg_dir", lambda: tmp_path / "nobody")
    return ffmpeg_folder


def test_a_macos_install_finds_ffmpeg_in_the_bundles_resources(monkeypatch, tmp_path):
    contents = tmp_path / "formcut.app" / "Contents"
    folder = installed(monkeypatch, tmp_path, contents / "MacOS" / "formcut-engine", contents / "Resources" / "ffmpeg")
    assert tools.bundle_dir() == folder


def test_a_windows_install_finds_ffmpeg_beside_the_engine(monkeypatch, tmp_path):
    install = tmp_path / "Programs" / "formcut"
    folder = installed(monkeypatch, tmp_path, install / "formcut-engine.exe", install / "ffmpeg")
    assert tools.bundle_dir() == folder


def test_a_linux_package_finds_ffmpeg_in_usr_lib(monkeypatch, tmp_path):
    # The AppImage (and a .deb or .rpm) has the engine in usr/bin and the
    # resources in usr/lib/formcut, as the 1.32.0 AppImage built on Linux showed.
    usr = tmp_path / "squashfs-root" / "usr"
    folder = installed(monkeypatch, tmp_path, usr / "bin" / "formcut-engine", usr / "lib" / "formcut" / "ffmpeg")
    assert tools.bundle_dir() == folder


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_a_plainly_named_bundle_is_adopted_without_writing(monkeypatch, tmp_path):
    folder = tmp_path / "Resources" / "ffmpeg"
    folder.mkdir(parents=True)
    (folder / tools._names("ffmpeg")[0]).write_text("program")
    folder.chmod(0o555)
    monkeypatch.setattr(tools, "bundle_dir", lambda: folder)
    monkeypatch.setenv("PATH", "/system")
    try:
        assert tools.prefer_bundled() == folder
        assert sorted(p.name for p in folder.iterdir()) == [tools._names("ffmpeg")[0]]
    finally:
        folder.chmod(0o755)


def workflow() -> str:
    return (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")


def test_the_release_bundles_ffmpeg_on_every_platform():
    text = workflow()
    step = text[text.index("- name: bundle ffmpeg") : text.index("- name: build the app")]
    assert "runner.os" not in step


def test_ffmpeg_is_staged_before_the_app_is_built():
    text = workflow()
    assert text.index("- name: bundle ffmpeg") < text.index("- name: build the app")


def test_the_release_checks_the_bundle_with_the_apps_own_check():
    text = workflow()
    step = text[text.index("- name: bundle ffmpeg") : text.index("- name: build the app")]
    assert "python setup/bundle_ffmpeg.py --target" in step
    script = (ROOT / "setup" / "bundle_ffmpeg.py").read_text(encoding="utf-8")
    assert "ffmpeg_fetch.install(" in script and "ffmpeg_fetch.pins(" in script


def test_a_local_mac_build_bundles_ffmpeg_as_the_release_does():
    script = (ROOT / "setup" / "build_macos_app").read_text(encoding="utf-8")
    assert script.index("setup/bundle_ffmpeg.py") < script.index("cargo tauri build")


def test_the_bundle_carries_the_staging_folder():
    config = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))
    assert config["bundle"]["resources"] == {"ffmpeg/": "ffmpeg/"}
    assert (ROOT / "src-tauri" / "ffmpeg" / "README.md").is_file()


def test_the_staging_folder_never_tracks_binaries():
    rules = (ROOT / "src-tauri" / "ffmpeg" / ".gitignore").read_text(encoding="utf-8").split()
    assert rules[rules.index("*") :] == ["*", "!.gitignore", "!README.md"]
