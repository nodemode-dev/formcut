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
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


def bundle_dir() -> Path | None:
    """Where a packaged build keeps its binaries, if this is one."""
    explicit = os.environ.get("FORMCUT_FFMPEG_DIR")
    if explicit and Path(explicit).is_dir():
        return Path(explicit)
    if getattr(sys, "frozen", False):
        here = Path(sys.executable).resolve().parent
        for candidate in (here, here / "binaries", here.parent / "Resources" / "binaries"):
            if (candidate / "ffmpeg").exists() or (candidate / "ffmpeg.exe").exists():
                return candidate
    local = Path(__file__).resolve().parents[2] / "src-tauri" / "binaries"
    if (local / "ffmpeg").exists() or (local / "ffmpeg.exe").exists():
        return local
    return None


def prefer_bundled() -> Path | None:
    """Put the bundled directory first on PATH, so every call finds it.

    Doing it here rather than at each of the thirty-odd call sites means a
    replaced binary is picked up everywhere at once, including by code that
    spells the program's name as a plain string.
    """
    folder = bundle_dir()
    if not folder:
        return None
    current = os.environ.get("PATH", "")
    if str(folder) not in current.split(os.pathsep):
        os.environ["PATH"] = os.pathsep.join([str(folder), current])
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
    result = subprocess.run([ffmpeg(), "-hide_banner", "-i", str(path)],
                            capture_output=True, text=True, check=False, timeout=120)
    text = result.stderr
    streams: list[dict] = []
    video = _VIDEO.search(text) or _VIDEO_NO_FPS.search(text)
    if video:
        groups = video.groups()
        rate = float(groups[3]) if len(groups) > 3 else 0.0
        streams.append({
            "codec_type": "video", "codec_name": groups[0],
            "width": int(groups[1]), "height": int(groups[2]),
            "avg_frame_rate": f"{rate}/1" if rate else "0/0",
            "r_frame_rate": f"{rate}/1" if rate else "0/0",
        })
    audio = _AUDIO.search(text)
    if audio:
        streams.append({
            "codec_type": "audio", "codec_name": audio.group(1),
            "sample_rate": audio.group(2),
            "channels": 2 if "stereo" in audio.group(3) else 1,
        })
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
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", str(path)],
                capture_output=True, text=True, check=False, timeout=120,
            )
            if out.returncode == 0 and out.stdout.strip():
                return json.loads(out.stdout)
        except (subprocess.SubprocessError, ValueError):
            pass
    return _from_ffmpeg(Path(path))
