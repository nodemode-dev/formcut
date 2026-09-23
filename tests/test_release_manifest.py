"""setup/release_manifest.py: every zip, what it is, and how to check it."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "setup" / "release_manifest.py"


def _load():
    spec = importlib.util.spec_from_file_location("release_manifest", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_each_zip_is_listed_with_its_platform_size_and_checksum(tmp_path):
    names = {
        "formcut-9.9.9-macos-arm64.zip": b"mac",
        "formcut-9.9.9-windows-x86_64.zip": b"win",
        "formcut-9.9.9-linux-x86_64.zip": b"linux",
    }
    for name, data in names.items():
        (tmp_path / name).write_bytes(data)
    result = _load().manifest("9.9.9", tmp_path)
    assert result["version"] == "9.9.9" and result["ffmpeg"]["licence"] == "LGPL-2.1-or-later"
    by_file = {asset["file"]: asset for asset in result["assets"]}
    assert set(by_file) == set(names)
    linux = by_file["formcut-9.9.9-linux-x86_64.zip"]
    assert (linux["platform"], linux["arch"], linux["bytes"], linux["minimum_os"]) == ("linux", "x86_64", 5, "glibc 2.35")
    assert linux["sha256"] == hashlib.sha256(b"linux").hexdigest()


def test_a_zip_this_release_does_not_make_stops_it(tmp_path):
    (tmp_path / "formcut-9.9.9-beos-x86.zip").write_bytes(b"?")
    with pytest.raises(SystemExit, match="not a file this release makes"):
        _load().manifest("9.9.9", tmp_path)


def test_the_phone_apps_are_listed_with_their_minimum_os(tmp_path):
    (tmp_path / "formcut-9.9.9-android-arm64.apk").write_bytes(b"apk")
    (tmp_path / "formcut-9.9.9-ios-arm64.ipa").write_bytes(b"ipa")
    by_platform = {asset["platform"]: asset for asset in _load().manifest("9.9.9", tmp_path)["assets"]}
    assert by_platform["android"]["minimum_os"] == "Android 7.0 (API 24)" and by_platform["android"]["arch"] == "arm64"
    assert by_platform["ios"]["minimum_os"] == "iOS 14" and by_platform["ios"]["file"] == "formcut-9.9.9-ios-arm64.ipa"
