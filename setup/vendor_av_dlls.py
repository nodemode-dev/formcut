"""Puts the LGPL FFmpeg DLLs beside PyAV on Windows, then checks that PyAV imports.

PyAV built from source (setup/build_lgpl_av.bat) links av/_core.pyd and the rest
to avcodec-*.dll, avformat-*.dll and the other FFmpeg DLLs in
backend/.lgpl-ffmpeg/bin. Since Python 3.8 Windows does not look on PATH for the
DLLs an extension module needs, so `import av` failed with "DLL load failed
while importing _core" in every later process: PyInstaller's PyAV hook could not
import it and froze an engine without PyAV. The DLLs beside the .pyd files are
found by the loader, as the DLLs PyPI's PyAV wheels carry are.

    python setup/vendor_av_dlls.py <ffmpeg prefix> [--av-dir DIR] [--python EXE]
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path


def ffmpeg_dlls(prefix: Path) -> list[Path]:
    """The DLLs in the prefix's bin folder; a prefix without any is refused."""
    found = sorted(p for p in (Path(prefix) / "bin").glob("*.dll") if p.is_file())
    if not found:
        raise SystemExit(f"vendor-av: no FFmpeg DLLs in {Path(prefix) / 'bin'}; run setup/build_lgpl_av.bat first")
    return found


def copy_beside(prefix: Path, av_dir: Path) -> list[Path]:
    """Copies every FFmpeg DLL into PyAV's package folder, replacing older copies."""
    return [Path(shutil.copy2(dll, Path(av_dir) / dll.name)) for dll in ffmpeg_dlls(prefix)]


def imports_av(python: str, extra_path: Path | None = None) -> tuple[bool, str]:
    """Imports PyAV in a fresh process, as PyInstaller's hook and the engine do."""
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    if extra_path is not None:
        env["PYTHONPATH"] = str(extra_path)
    run = subprocess.run(
        [python, "-c", "import av; print(av.__version__)"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    detail = (run.stdout + run.stderr).strip()
    return run.returncode == 0, detail


def pyav_dir() -> Path:
    """PyAV's package folder, found without importing it (the import is what fails)."""
    spec = importlib.util.find_spec("av")
    if spec is None or not spec.origin:
        raise SystemExit("vendor-av: PyAV is not installed in this Python")
    return Path(spec.origin).parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("prefix", type=Path)
    parser.add_argument("--av-dir", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-import", action="store_true", help="copy only (tests)")
    args = parser.parse_args(argv)
    av_dir = args.av_dir or pyav_dir()
    copied = copy_beside(args.prefix, av_dir)
    print(f"vendor-av: {len(copied)} FFmpeg DLLs beside PyAV in {av_dir}")
    if args.skip_import:
        return 0
    ok, detail = imports_av(args.python)
    if not ok:
        print(f"vendor-av: PyAV still does not import:\n{detail}")
        return 1
    print(f"vendor-av: PyAV {detail.splitlines()[-1]} imports")
    return 0


if __name__ == "__main__":
    sys.exit(main())
