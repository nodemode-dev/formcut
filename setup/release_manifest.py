#!/usr/bin/env python3
"""Write a formcut release's manifest.json: what each zip is, and how to check it.

    python setup/release_manifest.py --version 1.33.0 --dir release-dist > manifest.json

For each zip, installer and phone app: its platform, architecture, kind (zip,
installer, apk or ipa), size, SHA-256 and minimum OS; with the
version, the commit it was built from, when, and the ffmpeg release bundled in it.
The formcut.studio site and anything else can read this rather than parse file names.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MINIMUM_OS = {"macos": "macOS 14", "windows": "Windows 10", "linux": "glibc 2.35"}
# The phone apps: Tauri 2's defaults, which mobile/src-tauri/tauri.conf.json does not change.
MOBILE = {".apk": ("android", "arm64", "Android 7.0 (API 24)"), ".ipa": ("ios", "arm64", "iOS 14")}


def _platforms() -> dict[str, tuple[str, str]]:
    spec = importlib.util.spec_from_file_location("package_release", ROOT / "setup" / "package_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PLATFORMS


def manifest(version: str, folder: Path) -> dict:
    known = {f"formcut-{version}-{platform}-{arch}.zip": (platform, arch) for platform, arch in _platforms().values()}
    for platform, arch in _platforms().values():
        if platform == "windows":
            known[f"formcut-{version}-{platform}-{arch}-setup.exe"] = (platform, arch)
    for suffix, (platform, arch, _) in MOBILE.items():
        known[f"formcut-{version}-{platform}-{arch}{suffix}"] = (platform, arch)
    minimum = {**MINIMUM_OS, **{platform: floor for platform, _, floor in MOBILE.values()}}
    assets = []
    for path in sorted(p for p in folder.glob("formcut-*") if p.suffix in (".zip", ".exe", *MOBILE)):
        if path.name not in known:
            raise SystemExit(f"{path.name} is not a file this release makes")
        platform, arch = known[path.name]
        assets.append(
            {
                "platform": platform,
                "arch": arch,
                "kind": "installer" if path.name.endswith("-setup.exe") else path.suffix.lstrip("."),
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "minimum_os": minimum[platform],
            }
        )
    record = json.loads((ROOT / "src-tauri" / "binaries" / "ffmpeg-licence.json").read_text(encoding="utf-8"))
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()
    return {
        "name": "formcut",
        "version": version,
        "commit": commit,
        "published": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repository": "https://github.com/nodemode-ai/formcut",
        "ffmpeg": {"release": record.get("release") or record["source"]["ffmpeg"]["version"], "licence": "LGPL-2.1-or-later"},
        "assets": assets,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True)
    parser.add_argument("--dir", type=Path, default=ROOT / "release-dist")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        raise SystemExit(f"{args.version} is not a version")
    print(json.dumps(manifest(args.version, args.dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
