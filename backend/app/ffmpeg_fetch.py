"""Fetch formcut's own LGPL ffmpeg on first run, when no ffmpeg is found.

The builds are published one archive per target on the formcut-binaries
release. Nothing in an archive is trusted: every file ffmpeg-licence.json
records for this machine, a record formcut carries, has to be in the archive
with that SHA-256 before any of it is placed in the per-person folder, and one
that is missing or different stops the fetch with nothing installed. An ffmpeg
a person already has, on PATH or placed by hand, is never replaced.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path

from . import jobs, tools

RELEASE = "https://github.com/nodemode-ai/formcut-binaries/releases/download"
DOCUMENTS = ("LGPL-2.1.txt", "THIRD-PARTY-NOTICES.txt", "README.md")


def record() -> dict | None:
    """ffmpeg-licence.json, beside the frozen engine or in a clone."""
    here = Path(__file__).resolve()
    for candidate in (
        Path(getattr(sys, "_MEIPASS", here.parent)) / "ffmpeg-licence.json",
        here.parents[2] / "src-tauri" / "binaries" / "ffmpeg-licence.json",
    ):
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except ValueError:
                return None
    return None


def pins(data: dict, triple: str) -> list[dict]:
    target = (data.get("targets") or {}).get(triple) or {}
    return [entry for entry in target.get("files") or [] if entry.get("path") and entry.get("sha256")]


def release(data: dict) -> str:
    """The release name, which tags the release and names its archives; the FFmpeg version without one."""
    return data.get("release") or ((data.get("source") or {}).get("ffmpeg") or {}).get("version", "")


def source(data: dict, triple: str) -> str:
    name = release(data)
    base = os.environ.get("FORMCUT_FFMPEG_RELEASE") or f"{RELEASE}/ffmpeg-{name}"
    return f"{base.rstrip('/')}/ffmpeg-lgpl-{name}-{triple}.tar.gz"


def outdated() -> bool:
    """formcut is running its own download, from another release than the record it carries.

    Only the per-person folder formcut filled itself counts, known by the record
    it wrote there, and only while it is the ffmpeg formcut uses: an ffmpeg a
    person placed by hand, named in FORMCUT_FFMPEG_DIR or has on PATH is never
    replaced. A new formcut with a rebuilt ffmpeg (7.1.5-2 after 7.1.5) would
    otherwise leave everyone who fetched the first one on it for good.
    """
    data, folder = record(), tools.user_ffmpeg_dir()
    if not data or not pins(data, tools.host_triple()) or tools.bundle_dir() != folder:
        return False
    try:
        have = json.loads((folder / "ffmpeg-licence.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return release(have) != release(data)


def needed() -> bool:
    return (tools.bundle_dir() is None and shutil.which("ffmpeg") is None) or outdated()


def _download(url: str, path: Path, report, cancelled) -> None:
    import httpx

    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        total, done = int(response.headers.get("content-length") or 0), 0
        with path.open("wb") as out:
            for chunk in response.iter_bytes(1 << 20):
                if cancelled():
                    raise InterruptedError("Cancelled")
                out.write(chunk)
                done += len(chunk)
                if total:
                    report(0.8 * done / total)


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def install(archive: Path, files: list[dict], folder: Path) -> int:
    """Check every recorded file inside the archive, then place them all; on any mismatch place none."""
    with tempfile.TemporaryDirectory() as scratch:
        with tarfile.open(archive) as bundle:
            bundle.extractall(scratch, filter="data")
        first = Path(files[0]["path"])
        root = None
        for hit in Path(scratch).rglob(first.name):
            candidate = hit
            for _ in first.parts:
                candidate = candidate.parent
            if (candidate / first).is_file():
                root = candidate
                break
        if root is None:
            raise ValueError(f"the archive has no {first}")
        for entry in files:
            path = root / entry["path"]
            if not path.is_file():
                raise ValueError(f"the archive has no {entry['path']}")
            if _digest(path) != entry["sha256"]:
                raise ValueError(f"{entry['path']} does not match formcut's record, so nothing was installed")
        folder.mkdir(parents=True, exist_ok=True)
        for entry in files:
            target = folder / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / entry["path"], target)
        # The licence documents always come from the archive, so a refresh brings
        # the notices for whatever the new build contains.
        for name in DOCUMENTS:
            if (root / name).is_file():
                shutil.copy2(root / name, folder / name)
    return len(files)


def fetch(report, cancelled) -> dict:
    data = record()
    if not data:
        raise ValueError("formcut's ffmpeg record is missing, so a download could not be checked")
    triple = tools.host_triple()
    files = pins(data, triple)
    if not files:
        raise ValueError(f"no ffmpeg build is recorded for {triple}")
    url, folder = source(data, triple), tools.user_ffmpeg_dir()
    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / "ffmpeg.tar.gz"
        _download(url, archive, report, cancelled)
        count = install(archive, files, folder)
    (folder / "ffmpeg-licence.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    getattr(tools.have, "cache_clear", lambda: None)()
    adopted = tools.prefer_bundled()
    report(1.0)
    return {"folder": str(folder), "files": count, "source": url, "adopted": str(adopted) if adopted else None}


def auto_fetch():
    """Start the fetch as a job when no ffmpeg is found; FORMCUT_FFMPEG_AUTO=0 turns it off."""
    if os.environ.get("FORMCUT_FFMPEG_AUTO", "1") == "0" or not needed():
        return None
    return jobs.submit("ffmpeg-setup", lambda _id, report, cancelled: fetch(report, cancelled))
