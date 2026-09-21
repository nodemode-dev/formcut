"""Finding ffmpeg, and doing without ffprobe.

formcut runs ffmpeg as a separate program rather than linking it. That is what
keeps the licences apart: the bundled build is LGPL-2.1, formcut is Apache-2.0,
and the two meet at a process boundary. It also means a person can replace the
binary with their own, which is the freedom the LGPL is there to protect, so the
bundled copy has to be the one that gets used: this module puts the bundle's
directory at the front of the search path, ahead of anything on the system.

An LGPL build configured with `--disable-programs --enable-ffmpeg` produces no
ffprobe, because ffprobe is a separate program rather than a part of ffmpeg.
Rather than require one, `probe` answers the same questions from ffmpeg's own
report when ffprobe is missing, so a bundle carrying ffmpeg alone is complete.
"""

from __future__ import annotations

import contextlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


def host_triple() -> str:
    """The target triple the bundled programs carry for this machine."""
    arch = "aarch64" if platform.machine().lower() in ("arm64", "aarch64") else "x86_64"
    if sys.platform == "darwin":
        return f"{arch}-apple-darwin"
    if os.name == "nt":
        return f"{arch}-pc-windows-msvc"
    return f"{arch}-unknown-linux-gnu"


def user_ffmpeg_dir() -> Path:
    """The per-person folder formcut looks in, outside the app.

    A signed macOS app refuses to open once a file is added inside it, so this
    is where a person puts ffmpeg by hand, and where a download lands.
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "formcut" / "ffmpeg"


def _names(program: str) -> tuple[str, str]:
    suffix = ".exe" if os.name == "nt" else ""
    return f"{program}{suffix}", f"{program}-{host_triple()}{suffix}"


def _holds_ffmpeg(folder: Path) -> bool:
    return any((folder / name).is_file() for name in _names("ffmpeg"))


def bundle_dir() -> Path | None:
    """formcut's own ffmpeg, if one has been put where it looks.

    In order: FORMCUT_FFMPEG_DIR, beside a packaged app, the per-person
    folder, and src-tauri/binaries in a clone. A folder counts if it holds
    ffmpeg under its plain name or under this machine's target triple. With
    none of these, formcut runs whatever ffmpeg is on PATH, the person's own.
    """
    explicit = os.environ.get("FORMCUT_FFMPEG_DIR")
    if explicit and _holds_ffmpeg(Path(explicit)):
        return Path(explicit)
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        here = Path(sys.executable).resolve().parent
        candidates += [
            here,
            here / "binaries",
            here.parent / "Resources" / "binaries",
            # Where an installer puts the bundled ffmpeg resource: beside the
            # engine on Windows, in the bundle's Resources on macOS.
            here / "ffmpeg",
            here.parent / "Resources" / "ffmpeg",
        ]
    candidates += [user_ffmpeg_dir(), Path(__file__).resolve().parents[2] / "src-tauri" / "binaries"]
    return next((c for c in candidates if _holds_ffmpeg(c)), None)


def _plain_names(folder: Path) -> None:
    """Give triple-named programs the plain names the backend runs them by.

    The name sits in the same folder as the program, so the folder its
    libraries are found from does not change. A symlink follows a replaced
    program; Windows gets a hard link, or a copy where links are refused. A
    file already under the plain name is never touched.
    """
    for program in ("ffmpeg", "ffprobe"):
        plain, tripled = (folder / name for name in _names(program))
        if plain.exists() or plain.is_symlink() or not tripled.is_file():
            continue
        with contextlib.suppress(OSError):
            if os.name != "nt":
                plain.symlink_to(tripled.name)
            else:
                try:
                    os.link(tripled, plain)
                except OSError:
                    shutil.copy2(tripled, plain)


def prefer_bundled() -> Path | None:
    """Put formcut's own ffmpeg first on PATH, so every call finds it.

    Doing it here rather than at each call site means a replaced binary is
    picked up everywhere at once, including by code that spells the program's
    name as a plain string, and by yt-dlp. Windows has no rpath: a program
    finds its DLLs beside itself or on PATH, and the bundle keeps them in
    lib-<triple>, so on Windows that folder goes on PATH as well. A folder
    that cannot be given the plain name is not adopted.
    """
    folder = bundle_dir()
    if not folder:
        return None
    _plain_names(folder)
    if not (folder / _names("ffmpeg")[0]).is_file():
        return None
    first = [folder]
    if os.name == "nt":
        first += sorted(d for d in folder.glob("lib-*") if d.is_dir())
    parts = [x for x in os.environ.get("PATH", "").split(os.pathsep) if x]
    missing = [str(d) for d in first if str(d) not in parts]
    if missing:
        os.environ["PATH"] = os.pathsep.join(missing + parts)
    return folder


@lru_cache(maxsize=2)
def have(program: str) -> bool:
    return shutil.which(program) is not None


def ffmpeg() -> str:
    return shutil.which("ffmpeg") or "ffmpeg"


def licence_note() -> dict:
    """What is shipped beside the binary, for the diagnostics panel."""
    folder = bundle_dir()
    if not folder:
        return {"bundled": False}
    record = folder / "ffmpeg-licence.json"
    note = {"bundled": True, "folder": str(folder), "ffprobe": have("ffprobe")}
    if record.is_file():
        with contextlib.suppress(ValueError):
            note.update(json.loads(record.read_text(encoding="utf-8")))
    note["licenceText"] = (folder / "LGPL-2.1.txt").is_file()
    return note


_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)")
_VIDEO = re.compile(r"Stream #\d+:\d+.*?: Video: (\w+).*?, (\d+)x(\d+).*?, ([\d.]+) fps", re.DOTALL)
_VIDEO_NO_FPS = re.compile(r"Stream #\d+:\d+.*?: Video: (\w+).*?, (\d+)x(\d+)")
_AUDIO = re.compile(r"Stream #\d+:\d+.*?: Audio: (\w+).*?, (\d+) Hz, ([^,]+)")
_BITRATE = re.compile(r"bitrate:\s*(\d+) kb/s")


def _from_ffmpeg(path: Path) -> dict:
    """The same shape ffprobe returns, read from ffmpeg's own report.

    ffmpeg writes what it found to stderr and exits with an error because no
    output was asked for; that error is expected and the report is the point.
    """
    result = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)], capture_output=True, text=True, check=False, timeout=120)
    text = result.stderr
    streams: list[dict] = []
    video = _VIDEO.search(text) or _VIDEO_NO_FPS.search(text)
    if video:
        groups = video.groups()
        rate = float(groups[3]) if len(groups) > 3 else 0.0
        streams.append(
            {
                "codec_type": "video",
                "codec_name": groups[0],
                "width": int(groups[1]),
                "height": int(groups[2]),
                "avg_frame_rate": f"{rate}/1" if rate else "0/0",
                "r_frame_rate": f"{rate}/1" if rate else "0/0",
            }
        )
    audio = _AUDIO.search(text)
    if audio:
        streams.append(
            {
                "codec_type": "audio",
                "codec_name": audio.group(1),
                "sample_rate": audio.group(2),
                "channels": 2 if "stereo" in audio.group(3) else 1,
            }
        )
    seconds = 0.0
    found = _DURATION.search(text)
    if found:
        hours, minutes, rest = found.groups()
        seconds = int(hours) * 3600 + int(minutes) * 60 + float(rest)
    fmt = {"duration": f"{seconds:.6f}", "format_name": path.suffix.lstrip(".")}
    rate = _BITRATE.search(text)
    if rate:
        fmt["bit_rate"] = str(int(rate.group(1)) * 1000)
    return {"streams": streams, "format": fmt}


def probe(path: Path) -> dict:
    """Stream and format facts, from ffprobe when there is one."""
    if have("ffprobe"):
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                capture_output=True,
                text=True,
                check=False,
                timeout=120,
            )
            if out.returncode == 0 and out.stdout.strip():
                return json.loads(out.stdout)
        except (subprocess.SubprocessError, ValueError):
            pass
    return _from_ffmpeg(Path(path))
