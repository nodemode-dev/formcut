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
    with pytest.raises(SystemExit, match="not a zip this release makes"):
        _load().manifest("9.9.9", tmp_path)
