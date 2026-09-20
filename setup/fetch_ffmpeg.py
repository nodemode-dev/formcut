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
# LGPL builds first, and by default. formcut is Apache-2.0 and runs ffmpeg as a
# separate program, so an LGPL ffmpeg beside it leaves both licences intact and
# leaves the person free to replace the binary. A GPL build would make the
# bundle GPL, so it is available only to someone who asks for it by name.
SOURCES: dict[str, dict] = {
    "aarch64-apple-darwin": {
        "url": "local:ffmpeg-aarch64-apple-darwin",
        "licence": "LGPL-2.1-or-later",
        "members": ("ffmpeg",),
        "configure": "--disable-gpl --disable-nonfree --enable-videotoolbox "
                     "--disable-programs --enable-ffmpeg --disable-doc --disable-debug --arch=arm64",
    },
    "x86_64-apple-darwin": {
        "url": "",
        "licence": "LGPL-2.1-or-later",
        "members": ("ffmpeg",),
        "configure": "run setup/build_ffmpeg_lgpl.sh on that platform",
    },
    "x86_64-unknown-linux-gnu": {
        "url": "",
        "licence": "LGPL-2.1-or-later",
        "members": ("ffmpeg",),
        "configure": "run setup/build_ffmpeg_lgpl.sh on that platform",
    },
    "x86_64-pc-windows-msvc": {
        "url": "",
        "licence": "LGPL-2.1-or-later",
        "members": ("ffmpeg.exe",),
        "configure": "run setup/build_ffmpeg_lgpl.sh on that platform",
    },
}

# Kept so a GPL build can still be chosen deliberately; choosing one makes the
# distributed bundle GPL-3.0 and formcut's own Apache-2.0 terms no longer
# describe what was shipped.
GPL_SOURCES: dict[str, str] = {
    "x86_64-unknown-linux-gnu": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz",
    "aarch64-apple-darwin": "https://evermeet.cx/ffmpeg/getrelease/zip",
    "x86_64-apple-darwin": "https://evermeet.cx/ffmpeg/getrelease/zip",
    "x86_64-pc-windows-msvc": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
}


ROOT = Path(__file__).resolve().parent.parent


def _record(out: Path, target: str, entry: dict, digest: str) -> None:
    """What was shipped, so the bundle can always say where it came from."""
    (out / "ffmpeg-licence.json").write_text(json.dumps({
        "target": target, "licence": entry["licence"], "configure": entry.get("configure", ""),
        "programs": list(entry["members"]), "sha256": digest,
        "source": "https://ffmpeg.org/download.html",
    }, indent=2), encoding="utf-8")
    for name in ("LGPL-2.1.txt", "README-ffmpeg.md"):
        supplied = ROOT / "src-tauri" / "binaries" / name
        if supplied.is_file():
            shutil.copy(supplied, out / name)


def fetch(target: str, out: Path, allow_gpl: bool) -> int:
    entry = SOURCES.get(target)
    if not entry:
        print(f"no ffmpeg source recorded for {target}", file=sys.stderr)
        return 2
    if allow_gpl:
        url = GPL_SOURCES.get(target)
        if not url:
            print(f"no GPL build recorded for {target}", file=sys.stderr)
            return 3
        entry = {**entry, "url": url, "licence": "GPL-3.0",
                 "members": entry["members"] + (("ffprobe.exe",) if target.endswith("msvc") else ("ffprobe",))}
        print("shipping a GPL ffmpeg: the bundle you distribute is GPL-3.0, not Apache-2.0.", file=sys.stderr)
    source = str(entry.get("url") or "")
    if source.startswith("local:"):
        # A build supplied with the repository, already LGPL and already checked.
        supplied = ROOT / "src-tauri" / "binaries" / source.split(":", 1)[1]
        if not supplied.is_file():
            print(f"the supplied LGPL build is missing: {supplied}", file=sys.stderr)
            return 4
        out.mkdir(parents=True, exist_ok=True)
        target_name = "ffmpeg.exe" if target.endswith("msvc") else "ffmpeg"
        shutil.copy(supplied, out / target_name)
        (out / target_name).chmod(0o755)
        _record(out, target, entry, hashlib.sha256(supplied.read_bytes()).hexdigest())
        print(f"{target}: using the supplied {entry['licence']} build")
        return 0
    if not source:
        print(f"no LGPL build recorded for {target}.", file=sys.stderr)
        print(f"  {entry['configure']}", file=sys.stderr)
        print("  It writes the binary here and records its licence and checksum.", file=sys.stderr)
        print("or pass --allow-gpl to ship a GPL build knowingly.", file=sys.stderr)
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
