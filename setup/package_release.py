#!/usr/bin/env python3
"""Turn a built formcut into its platform's release zip, as the release publishes it.

    python setup/package_release.py --target aarch64-apple-darwin
    python setup/package_release.py --target x86_64-pc-windows-msvc
    python setup/package_release.py --target x86_64-unknown-linux-gnu

Each zip runs with nothing else installed:

- macOS: formcut.app, zipped with ditto where it exists so the bundle's
  permissions and metadata survive; unzip and open it.
- Windows: a formcut folder holding formcut.exe with formcut-engine.exe and the
  bundled ffmpeg beside it, which is where the app and the engine look for them;
  unzip and run formcut.exe. Beside the zip, the NSIS installer Tauri built
  (formcut-<version>-windows-<arch>-setup.exe), which installs the same three
  parts in the same layout: the engine as the externalBin sidecar beside
  formcut.exe and ffmpeg as the "ffmpeg/" resource beside both.
- Linux: the AppImage, one self-contained file; unzip and run it.

Every part the zip needs is checked first, so a build that lost one fails here
instead of publishing a zip that cannot start. Zips go to release-dist/ as
formcut-<version>-<platform>-<arch>.zip; the version is tauri.conf.json's.
"""

from __future__ import annotations

import argparse
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLATFORMS = {
    "aarch64-apple-darwin": ("macos", "arm64"),
    "x86_64-apple-darwin": ("macos", "x86_64"),
    "x86_64-pc-windows-msvc": ("windows", "x86_64"),
    "aarch64-pc-windows-msvc": ("windows", "arm64"),
    "x86_64-unknown-linux-gnu": ("linux", "x86_64"),
    "aarch64-unknown-linux-gnu": ("linux", "arm64"),
}
# The platform names formcompiler gives the files it publishes: it renames each zip and installer to
# formcut-<version>-<platform>.zip and formcut-<version>-<platform>-setup.exe before setup/release_assets runs.
RELEASE_PLATFORMS = {
    "aarch64-apple-darwin": "macos-arm64",
    "x86_64-apple-darwin": "macos-x64",
    "x86_64-pc-windows-msvc": "windows-x64",
    "aarch64-pc-windows-msvc": "windows-arm64",
    "x86_64-unknown-linux-gnu": "linux-x64",
    "aarch64-unknown-linux-gnu": "linux-arm64",
}


def version() -> str:
    return json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))["version"]


def require(path: Path, what: str) -> Path:
    if not path.exists():
        raise SystemExit(f"{what} is missing: {path}; the build did not produce it, so nothing was packaged")
    return path


def write_zip(archive: Path, root: Path, base: Path) -> None:
    """Zip root (a file or a folder) with paths relative to base, keeping Unix modes."""
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        paths = [root] if root.is_file() else sorted([root, *root.rglob("*")])
        for path in paths:
            name = path.relative_to(base).as_posix() + ("/" if path.is_dir() else "")
            info = zipfile.ZipInfo(name)
            mode = path.lstat().st_mode
            info.external_attr = (mode & 0xFFFF) << 16 | (0x10 if path.is_dir() else 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            if path.is_symlink():
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                bundle.writestr(info, str(path.readlink()))
            elif path.is_dir():
                bundle.writestr(info, b"")
            else:
                bundle.writestr(info, path.read_bytes())


def package(triple: str, out: Path) -> Path:
    platform, arch = PLATFORMS[triple]
    release = ROOT / "src-tauri" / "target" / triple / "release"
    name = f"formcut-{version()}-{platform}-{arch}"
    out.mkdir(parents=True, exist_ok=True)
    archive = out / f"{name}.zip"
    archive.unlink(missing_ok=True)
    if platform == "macos":
        app = require(release / "bundle" / "macos" / "formcut.app", "formcut.app")
        require(app / "Contents" / "MacOS" / "formcut-engine", "the engine inside formcut.app")
        if shutil.which("ditto"):
            subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app), str(archive)], check=True)
        else:
            write_zip(archive, app, app.parent)
    elif platform == "windows":
        stage = out / name / "formcut"
        shutil.rmtree(stage.parent, ignore_errors=True)
        stage.mkdir(parents=True)
        for part in ("formcut.exe", "formcut-engine.exe"):
            shutil.copy2(require(release / part, part), stage / part)
        ffmpeg = release / "ffmpeg"
        if (ffmpeg / "ffmpeg.exe").is_file():
            shutil.copytree(ffmpeg, stage / "ffmpeg")
        else:
            print("note: no bundled ffmpeg; this zip fetches formcut's on first run")
        write_zip(archive, stage, stage.parent)
        shutil.rmtree(stage.parent)
        installers = sorted((release / "bundle" / "nsis").glob("*-setup.exe"))
        if installers:
            installer = out / f"{name}-setup.exe"
            shutil.copy2(installers[0], installer)
            print(f"packaged {installer.relative_to(ROOT)} ({installer.stat().st_size / 1048576:.1f} MB)")
        else:
            print("note: no NSIS installer was built; only the portable zip is packaged")
    else:
        images = sorted((release / "bundle" / "appimage").glob("*.AppImage"))
        image = require(images[0] if images else release / "bundle" / "appimage" / "formcut.AppImage", "the AppImage")
        image.chmod(image.stat().st_mode | 0o111)
        write_zip(archive, image, image.parent)
    print(f"packaged {archive.relative_to(ROOT)} ({archive.stat().st_size / 1048576:.1f} MB)")
    return archive


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, choices=sorted(PLATFORMS))
    parser.add_argument("--out", type=Path, default=ROOT / "release-dist")
    args = parser.parse_args()
    package(args.target, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
