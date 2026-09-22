"""The desktop app's release profile: the app is stripped, build-time crates are not.

cargo hands profile.release's strip to build scripts and procedural macros too
(checked: -C strip=symbols on the proc-macro's rustc line). Stripped, every
procedural macro failed with "can't find crate" on the owner's Mac (macOS 27,
rustc 1.97.1), and the same build succeeded with them left unstripped.
"""

import tomllib
from pathlib import Path

CARGO = Path(__file__).resolve().parent.parent / "src-tauri" / "Cargo.toml"


def test_the_app_is_stripped_and_build_time_crates_are_not():
    release = tomllib.loads(CARGO.read_text(encoding="utf-8"))["profile"]["release"]
    assert release["strip"] is True
    assert release["build-override"]["strip"] is False
