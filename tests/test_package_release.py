"""setup/package_release.py: each platform's zip holds what it needs to start, or none is made."""

from __future__ import annotations

import importlib.util
import os
import stat
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "setup" / "package_release.py"


@pytest.fixture
def packager(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("package_release", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "version", lambda: "9.9.9")
    monkeypatch.setattr(module.shutil, "which", lambda name: None)
    return module, tmp_path


def _file(path: Path, data: bytes = b"x", mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    path.chmod(mode)


def _modes(archive: Path) -> dict[str, int]:
    with zipfile.ZipFile(archive) as bundle:
        return {info.filename: (info.external_attr >> 16) & 0o777 for info in bundle.infolist()}


@pytest.mark.skipif(os.name == "nt", reason="zip modes come from POSIX permissions; these zips are packaged on macOS and Linux")
def test_linux_ships_the_appimage_executable(packager):
    module, root = packager
    release = root / "src-tauri" / "target" / "x86_64-unknown-linux-gnu" / "release"
    _file(release / "bundle" / "appimage" / "formcut_9.9.9_amd64.AppImage", b"appimage", 0o644)
    archive = module.package("x86_64-unknown-linux-gnu", root / "out")
    assert archive.name == "formcut-9.9.9-linux-x86_64.zip"
    assert _modes(archive) == {"formcut_9.9.9_amd64.AppImage": 0o755}


def test_windows_ships_a_folder_with_the_engine_and_ffmpeg_beside_the_app(packager):
    module, root = packager
    release = root / "src-tauri" / "target" / "x86_64-pc-windows-msvc" / "release"
    for part in ("formcut.exe", "formcut-engine.exe", "ffmpeg/ffmpeg.exe", "ffmpeg/lib-x86_64-pc-windows-msvc/avcodec-61.dll"):
        _file(release / part)
    archive = module.package("x86_64-pc-windows-msvc", root / "out")
    assert archive.name == "formcut-9.9.9-windows-x86_64.zip"
    files = {name for name in _modes(archive) if not name.endswith("/")}
    assert files == {
        "formcut/formcut.exe",
        "formcut/formcut-engine.exe",
        "formcut/ffmpeg/ffmpeg.exe",
        "formcut/ffmpeg/lib-x86_64-pc-windows-msvc/avcodec-61.dll",
    }
    assert not (root / "out" / "formcut-9.9.9-windows-x86_64").exists()


@pytest.mark.skipif(os.name == "nt", reason="zip modes come from POSIX permissions; these zips are packaged on macOS and Linux")
def test_macos_keeps_the_bundle_and_its_executables(packager):
    module, root = packager
    app = root / "src-tauri" / "target" / "aarch64-apple-darwin" / "release" / "bundle" / "macos" / "formcut.app"
    _file(app / "Contents" / "MacOS" / "formcut", mode=0o755)
    _file(app / "Contents" / "MacOS" / "formcut-engine", mode=0o755)
    _file(app / "Contents" / "Info.plist")
    modes = _modes(module.package("aarch64-apple-darwin", root / "out"))
    assert modes["formcut.app/Contents/MacOS/formcut-engine"] & stat.S_IXUSR
    assert "formcut.app/Contents/Info.plist" in modes


def test_a_build_missing_its_engine_packages_nothing(packager):
    module, root = packager
    _file(root / "src-tauri" / "target" / "x86_64-pc-windows-msvc" / "release" / "formcut.exe")
    with pytest.raises(SystemExit, match=r"formcut-engine\.exe is missing"):
        module.package("x86_64-pc-windows-msvc", root / "out")
    assert not list((root / "out").glob("*.zip"))
