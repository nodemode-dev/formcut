"""Release profiles: nothing is stripped, the app included (FAMILY_TEST_PLAN section 9).

cargo strips procedural macros with everything else in a release build:
-C strip=symbols under strip = true, and -C strip=debuginfo even with no strip
setting at all (both checked on their rustc lines). On the owner's Mac (macOS 27,
rustc 1.97.1) a stripped procedural macro cannot be loaded, "can't find crate",
which broke the app's build and then formcut_native's; every Cargo project in the
repository therefore sets [profile.release.build-override] strip = false.
"""

import subprocess
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TRACKED = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
MANIFESTS = sorted(path for path in TRACKED if path.endswith("Cargo.toml"))


def test_every_cargo_project_is_covered():
    assert {"src-tauri/Cargo.toml", "backend/native/Cargo.toml", "mobile/src-tauri/Cargo.toml"} <= set(MANIFESTS)


@pytest.mark.parametrize("manifest", MANIFESTS)
def test_build_time_crates_are_left_unstripped(manifest):
    profile = tomllib.loads((ROOT / manifest).read_text(encoding="utf-8"))["profile"]["release"]
    assert profile["build-override"]["strip"] is False


def test_the_app_is_not_stripped():
    release = tomllib.loads((ROOT / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8"))["profile"]["release"]
    assert release["strip"] is False


def test_the_kernel_library_is_not_stripped():
    # Python loads it as rustc loads a procedural macro; see backend/native/Cargo.toml.
    release = tomllib.loads((ROOT / "backend" / "native" / "Cargo.toml").read_text(encoding="utf-8"))["profile"]["release"]
    assert release["strip"] is False
