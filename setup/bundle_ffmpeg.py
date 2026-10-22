#!/usr/bin/env python3
"""Stage formcut's verified LGPL ffmpeg in src-tauri/ffmpeg, where the app bundles it.

The macOS and Windows apps carry ffmpeg from the formcut-binaries release, every
file checked against src-tauri/binaries/ffmpeg-licence.json by the same code the
app's first-run fetch uses; a file that differs fails the build. The programs are
staged under their plain names, so an installed app, which cannot be written to,
needs no links. A target with no published build, or a release that cannot be
reached, is noted and nothing is staged: that app fetches ffmpeg on first run.

The folder is emptied first, all but its README.md and .gitignore, so a build for
one target never carries another's files (an Intel build after an Apple Silicon
one, say).

    python setup/bundle_ffmpeg.py --target aarch64-apple-darwin

Run by setup/build_release and setup/build_macos_app, in an environment
with the engine's requirements installed.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STAGE = ROOT / "src-tauri" / "ffmpeg"
KEEP = {"README.md", ".gitignore"}


def clear(stage: Path) -> None:
    for entry in stage.iterdir():
        if entry.name in KEEP:
            continue
        if entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry)
        else:
            entry.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="the Rust target triple the app is built for")
    triple = parser.parse_args().target

    sys.path.insert(0, str(ROOT / "backend"))
    from app import ffmpeg_fetch

    record = ffmpeg_fetch.record()
    files = ffmpeg_fetch.pins(record, triple)
    clear(STAGE)
    if not files:
        print(f"::notice::no ffmpeg build is recorded for {triple}; this app fetches it on first run")
        return 0
    url = ffmpeg_fetch.source(record, triple)
    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / "ffmpeg.tar.gz"
        try:
            urllib.request.urlretrieve(url, archive)  # noqa: S310 - the record's own release address
        except OSError as error:
            print(f"::notice::{url} is not published ({error}); this app fetches ffmpeg on first run")
            return 0
        count = ffmpeg_fetch.install(archive, files, STAGE)
    suffix = ".exe" if triple.endswith("windows-msvc") else ""
    for program in ("ffmpeg", "ffprobe"):
        (STAGE / f"{program}-{triple}{suffix}").rename(STAGE / f"{program}{suffix}")
    print(f"bundled {count} files from {url}, each matching the record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
