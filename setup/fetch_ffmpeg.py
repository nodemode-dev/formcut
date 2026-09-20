#!/usr/bin/env python3
"""Fetch ffmpeg and ffprobe for a release bundle.

The gaps document asks that ffmpeg travel inside the app so nothing has to be on
the user's PATH, and that the licence of the build shipped is checked. Both
belong in one place, so this script records the licence alongside the binaries
it fetches and refuses a build whose licence is not recorded.

It is written for the release workflow and has not been run in this repository's
development environment, which has no network access. Running it once per target
before the first release is part of that release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

# Each entry names a build whose licence permits redistribution. LGPL builds are
# preferred: a GPL ffmpeg would impose its own terms on anything it ships with.
SOURCES: dict[str, dict] = {
    "x86_64-unknown-linux-gnu": {
        "url": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
        "licence": "GPL-3.0 (static build) — replace with an LGPL build before shipping a proprietary bundle",
        "members": ("ffmpeg", "ffprobe"),
    },
    "aarch64-apple-darwin": {
        "url": "https://evermeet.cx/ffmpeg/getrelease/zip",
        "licence": "GPL-3.0 — replace with an LGPL build before shipping a proprietary bundle",
        "members": ("ffmpeg",),
    },
    "x86_64-apple-darwin": {
        "url": "https://evermeet.cx/ffmpeg/getrelease/zip",
        "licence": "GPL-3.0 — replace with an LGPL build before shipping a proprietary bundle",
        "members": ("ffmpeg",),
    },
    "x86_64-pc-windows-msvc": {
        "url": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "licence": "GPL-3.0 — replace with an LGPL build before shipping a proprietary bundle",
        "members": ("ffmpeg.exe", "ffprobe.exe"),
    },
}


def fetch(target: str, out: Path, allow_gpl: bool) -> int:
    entry = SOURCES.get(target)
    if not entry:
        print(f"no ffmpeg source recorded for {target}", file=sys.stderr)
        return 2
    if "GPL" in entry["licence"] and not allow_gpl:
        print(f"the recorded build for {target} is {entry['licence']}.", file=sys.stderr)
        print("Pass --allow-gpl to ship it knowingly, or record an LGPL build first.", file=sys.stderr)
        return 3
    out.mkdir(parents=True, exist_ok=True)
    archive = out / f"ffmpeg-{target}"
    urllib.request.urlretrieve(entry["url"], archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as bundle:
            for name in bundle.namelist():
                base = Path(name).name
                if base in entry["members"]:
                    with bundle.open(name) as source, (out / base).open("wb") as target_file:
                        shutil.copyfileobj(source, target_file)
    else:
        with tarfile.open(archive) as bundle:
            for member in bundle.getmembers():
                base = Path(member.name).name
                if base in entry["members"]:
                    extracted = bundle.extractfile(member)
                    if extracted:
                        (out / base).write_bytes(extracted.read())
    archive.unlink(missing_ok=True)
    for base in entry["members"]:
        binary = out / base
        if not binary.is_file():
            print(f"{base} was not found in the archive", file=sys.stderr)
            return 4
        binary.chmod(0o755)
    (out / "ffmpeg-licence.json").write_text(json.dumps({
        "target": target, "url": entry["url"], "licence": entry["licence"], "sha256": digest,
    }, indent=2), encoding="utf-8")
    print(f"{target}: fetched {', '.join(entry['members'])} under {entry['licence']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=sorted(SOURCES))
    parser.add_argument("--out", type=Path, default=Path("src-tauri/binaries"))
    parser.add_argument("--allow-gpl", action="store_true")
    parser.add_argument("--list", action="store_true", help="show the recorded sources and exit")
    args = parser.parse_args()
    if args.list:
        for name, entry in SOURCES.items():
            print(f"{name:32s} {entry['licence']}")
        return 0
    return fetch(args.target, args.out, args.allow_gpl)


if __name__ == "__main__":
    raise SystemExit(main())
