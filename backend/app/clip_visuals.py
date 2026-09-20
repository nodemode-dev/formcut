"""Timeline clip visuals: an audio envelope and a strip of frames.

Both are derived once per media item and cached on disk, because a timeline
redraws on every zoom and trim and must never wait on ffmpeg to do it. Both are
computed over the whole media, not the clip's trimmed range: a clip's range is a
window onto its media, so the interface can slice a cached whole rather than ask
for a new render whenever a handle moves.
"""

import json
import struct
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from .media import MEDIA_DIR, _find
from .paths import DATA_DIR

router = APIRouter(prefix="/api/media", tags=["clip visuals"])


def _source(media_id: str) -> Path:
    """Resolve a stored media file the same way the file endpoint does."""
    matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not matches:
        raise HTTPException(status_code=404, detail="file missing")
    return matches[0]


PEAK_DIR = DATA_DIR / "peaks"
STRIP_DIR = DATA_DIR / "filmstrips"

# An envelope needs enough buckets that a clip zoomed to fill the timeline still
# looks like a waveform, and few enough that the payload stays small.
BUCKETS = 2000
SAMPLE_RATE = 8000
# A strip of 40 frames at 96 px wide is about 120 kB as jpeg and enough that a
# clip zoomed in still shows motion rather than one repeated frame.
STRIP_FRAMES = 40
STRIP_WIDTH = 96


@router.get("/{media_id}/peaks")
def get_peaks(media_id: str) -> FileResponse:
    item = _find(media_id)
    if item["kind"] not in ("audio", "video"):
        raise HTTPException(status_code=422, detail="this media has no audio to measure")
    cache = PEAK_DIR / f"{media_id}-{BUCKETS}.json"
    if not cache.exists():
        PEAK_DIR.mkdir(parents=True, exist_ok=True)
        data = _envelope(_source(media_id), float(item.get("duration") or 0.0))
        if data is None:
            raise HTTPException(status_code=422, detail="no audio track to measure")
        cache.write_text(json.dumps(data))
    return FileResponse(cache, media_type="application/json")


@router.get("/{media_id}/filmstrip")
def get_filmstrip(media_id: str, frames: int = Query(STRIP_FRAMES, ge=4, le=120)) -> FileResponse:
    item = _find(media_id)
    if item["kind"] not in ("video", "image"):
        raise HTTPException(status_code=422, detail="this media has no frames to strip")
    cache = STRIP_DIR / f"{media_id}-{frames}.jpg"
    if not cache.exists():
        STRIP_DIR.mkdir(parents=True, exist_ok=True)
        if not _strip(_source(media_id), cache, item["kind"], float(item.get("duration") or 0.0), frames):
            raise HTTPException(status_code=422, detail="could not read frames from this media")
    return FileResponse(cache, media_type="image/jpeg")


def _envelope(src: Path, duration: float) -> dict | None:
    """Decode to mono 16-bit at a low rate and reduce it to min and max per bucket.

    ffmpeg does the decoding and the downsampling; this only reduces, so the cost
    is linear in the decoded samples and independent of how the clip is later
    trimmed or zoomed.
    """
    cmd = [
        "ffmpeg",
        "-v",
        "quiet",
        "-i",
        str(src),
        "-map",
        "a:0",
        "-ac",
        "1",
        "-ar",
        str(SAMPLE_RATE),
        "-f",
        "s16le",
        "-",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, check=False, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return None
    raw = out.stdout
    if out.returncode != 0 or len(raw) < 2:
        return None
    total = len(raw) // 2
    samples = struct.unpack(f"<{total}h", raw[: total * 2])
    buckets = min(BUCKETS, max(1, total))
    size = total / buckets
    lows: list[int] = []
    highs: list[int] = []
    for index in range(buckets):
        start = int(index * size)
        end = max(start + 1, int((index + 1) * size))
        window = samples[start:end]
        lows.append(min(window))
        highs.append(max(window))
    measured = total / SAMPLE_RATE
    return {
        "duration": round(measured if measured > 0 else duration, 4),
        "buckets": buckets,
        # Normalised to -1..1 and rounded: three decimals is finer than a pixel
        # at any zoom the timeline offers, and keeps the payload small.
        "low": [round(value / 32768, 3) for value in lows],
        "high": [round(value / 32768, 3) for value in highs],
    }


def _strip(src: Path, dest: Path, kind: str, duration: float, frames: int) -> bool:
    """One row of frames, evenly spaced across the media, as a single jpeg."""
    if kind == "image":
        cmd = ["ffmpeg", "-v", "quiet", "-y", "-i", str(src), "-frames:v", "1", "-vf", f"scale={STRIP_WIDTH}:-2", str(dest)]
    else:
        span = max(duration, 0.1)
        # Sample at a rate that yields the requested count across the media, then
        # tile the result into one row. fps must stay above zero for short media.
        rate = max(frames / span, 0.01)
        cmd = [
            "ffmpeg",
            "-v",
            "quiet",
            "-y",
            "-i",
            str(src),
            "-vf",
            f"fps={rate:.6f},scale={STRIP_WIDTH}:-2,tile={frames}x1",
            "-frames:v",
            "1",
            "-q:v",
            "4",
            str(dest),
        ]
    try:
        subprocess.run(cmd, capture_output=True, check=False, timeout=180)
    except (OSError, subprocess.SubprocessError):
        return False
    return dest.exists() and dest.stat().st_size > 0
