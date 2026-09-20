"""The optional H.264 add-on.

formcut ships LGPL ffmpeg, which has no software H.264 encoder: libx264 is GPL,
and bundling it would make the distributed whole GPL. Machines with hardware
encoding never notice, because encoder detection finds videotoolbox,
mediafoundation, nvenc, qsv or vaapi and confirms it by encoding. Machines
without one have no software H.264 path at all.

This module is that path, arranged so it changes nothing about formcut's own
licence. The add-on is **not part of the build and is not distributed with it**:
a person installs it themselves, into their own data directory, and formcut uses
it if it is there. What they install is an ffmpeg binary that can encode H.264;
whatever licence that binary carries is a matter between them and whoever built
it, and it never touches the Apache-2.0 terms of formcut or the LGPL terms of
the ffmpeg formcut ships.

The mechanism is deliberately dull: a folder, a binary, and a check that it can
actually encode before it is offered.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from .paths import DATA_DIR

router = APIRouter(prefix="/api/addons", tags=["addons"])

ADDON_DIR = DATA_DIR / "addons" / "h264"
BINARY = ADDON_DIR / ("ffmpeg.exe" if Path("/").drive else "ffmpeg")


def addon_path() -> Path | None:
    """The installed add-on binary, if there is one."""
    for candidate in (ADDON_DIR / "ffmpeg", ADDON_DIR / "ffmpeg.exe"):
        if candidate.is_file():
            return candidate
    return None


def _encoders(binary: Path) -> set[str]:
    try:
        listed = subprocess.run([str(binary), "-hide_banner", "-encoders"], capture_output=True, text=True, check=False, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return set()
    names = set()
    for line in listed.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith(("V", "A")):
            names.add(parts[1])
    return names


def _confirm(binary: Path, encoder: str) -> bool:
    """Encode two generated frames, because a listed encoder can still fail."""
    try:
        probe = subprocess.run(
            [
                str(binary),
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=320x240:rate=30:duration=0.1",
                "-frames:v",
                "2",
                "-c:v",
                encoder,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            check=False,
            timeout=90,
        )
        return probe.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def h264_encoder() -> tuple[Path, str] | None:
    """The add-on's H.264 encoder, if one is installed and works.

    Checked once per process and on install, not per export: probing spawns a
    process, and an export should not pay for that every time.
    """
    binary = addon_path()
    if not binary:
        return None
    record = ADDON_DIR / "addon.json"
    if record.is_file():
        try:
            saved = json.loads(record.read_text(encoding="utf-8"))
            if saved.get("encoder") and saved.get("confirmed"):
                return binary, str(saved["encoder"])
        except ValueError:
            pass
    available = _encoders(binary)
    for candidate in ("libx264", "libopenh264", "h264_videotoolbox", "h264_nvenc", "h264_qsv"):
        if candidate in available and _confirm(binary, candidate):
            record.write_text(
                json.dumps(
                    {
                        "encoder": candidate,
                        "confirmed": True,
                        "checked": time.time(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return binary, candidate
    return None


def status() -> dict:
    """What the interface shows: installed, working, and which encoder."""
    binary = addon_path()
    if not binary:
        return {"installed": False, "why": "formcut ships an LGPL ffmpeg, which has no software H.264 encoder"}
    found = h264_encoder()
    return {
        "installed": True,
        "path": str(binary),
        "working": found is not None,
        "encoder": found[1] if found else None,
        "note": "installed by you, not shipped with formcut; its licence is separate",
    }


@router.get("/h264")
def h264_status() -> dict:
    return status()


@router.post("/h264", status_code=201)
async def install_h264(file: UploadFile) -> dict:
    """Install an ffmpeg binary that can encode H.264.

    The file is checked before it is kept: a binary that cannot actually encode
    H.264 is rejected rather than installed and discovered later during an
    export that fails.
    """
    ADDON_DIR.mkdir(parents=True, exist_ok=True)
    staging = ADDON_DIR / "incoming"
    raw = await file.read()
    if len(raw) > 400_000_000:
        raise HTTPException(status_code=413, detail="that file is implausibly large for an ffmpeg binary")
    staging.write_bytes(raw)
    staging.chmod(0o755)
    try:
        available = _encoders(staging)
        usable = next(
            (
                name
                for name in ("libx264", "libopenh264", "h264_videotoolbox", "h264_nvenc", "h264_qsv")
                if name in available and _confirm(staging, name)
            ),
            None,
        )
        if not usable:
            raise HTTPException(status_code=422, detail="that binary runs but cannot encode H.264")
        target = ADDON_DIR / ("ffmpeg.exe" if file.filename and file.filename.endswith(".exe") else "ffmpeg")
        staging.replace(target)
        target.chmod(0o755)
        (ADDON_DIR / "addon.json").write_text(
            json.dumps(
                {
                    "encoder": usable,
                    "confirmed": True,
                    "checked": time.time(),
                    "source": "installed by the user",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return status()
    finally:
        staging.unlink(missing_ok=True)


@router.delete("/h264", status_code=204, response_model=None)
def remove_h264():
    if ADDON_DIR.is_dir():
        shutil.rmtree(ADDON_DIR, ignore_errors=True)
