"""The release build scripts: what they build, and what they write for the release.

The name is kept from when a workflow here did this. Now nodemode-ai/formcompiler
builds and publishes formcut, and calls setup/build_release, setup/build_phone and
setup/release_assets; when it runs, who starts it and the publishing live there.
These scripts cannot run here, so their rules are checked from the files: the
three targets, every platform checked, bundled and packaged the same way, the
phone apps built unsigned, the macOS app sealed and checked after packaging, and
the notes naming exactly the zips setup/package_release.py writes.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = (ROOT / "setup" / "build_release").read_text(encoding="utf-8")
PHONE = (ROOT / "setup" / "build_phone").read_text(encoding="utf-8")
ASSETS = (ROOT / "setup" / "release_assets").read_text(encoding="utf-8")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "setup" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _targets() -> list[str]:
    return re.findall(r"^  (\S+)\) BUNDLES=", BUILD, re.MULTILINE)


def test_the_three_platforms_it_ships():
    assert _targets() == ["aarch64-apple-darwin", "x86_64-pc-windows-msvc", "x86_64-unknown-linux-gnu"]


def test_every_platform_is_checked_bundled_and_packaged_alike():
    assert '"native_kernels": true' in BUILD
    assert "setup/bundle_ffmpeg.py" in BUILD
    assert "setup/package_release.py" in BUILD
    for step in ("freeze the engine", "bundle ffmpeg", "build the app", "package the zip"):
        assert f'say "{step}"' in BUILD
    assert "setup/release_notes.py" in ASSETS and "setup/release_manifest.py" in ASSETS
    assert "SHA256SUMS" in ASSETS and "manifest.json" in ASSETS


def test_the_notes_name_exactly_the_zips_that_are_built():
    packager, notes = _load("package_release"), _load("release_notes")
    text = notes.notes("9.9.9")
    for target in _targets():
        platform, arch = packager.PLATFORMS[target]
        assert f"`formcut-9.9.9-{platform}-{arch}.zip`" in text


def test_the_phone_apps_are_built_unsigned_with_the_release_version():
    assert "tauri android build --debug --apk --target aarch64" in PHONE and "android-arm64.apk" in PHONE
    assert "tauri ios build --no-sign --target aarch64" in PHONE and "ios-arm64.ipa" in PHONE
    assert PHONE.count('--config "{\\"version\\":\\"$VERSION\\"}"') == 2


def test_the_macos_app_is_sealed_and_checked_as_a_download():
    """Unsealed, a downloaded app is 'damaged' on Apple silicon, with no way to open it."""
    import json

    mac = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))["bundle"]["macOS"]
    assert mac["signingIdentity"] == "-", "ad hoc: seals the bundle with no Apple account"
    assert mac["hardenedRuntime"] is False, "library validation would stop the one-file engine and OpenH264"
    sealed = BUILD.index('say "the downloaded macOS app is sealed"')
    assert BUILD.rindex('if [ "$RUNNER_OS" = macOS ]; then', 0, sealed) > BUILD.index('say "package the zip"')
    check = BUILD[sealed:]
    assert "ditto -x -k release-dist/*.zip" in check and "codesign --verify --deep --strict" in check
