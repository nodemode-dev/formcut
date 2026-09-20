"""Where the disk went.

The home screen shows what the app has accumulated, so a person can see why a
data directory is large and clear the parts that are derived. Everything here is
measured, never estimated: caches can be rebuilt, media and projects cannot, so
they are reported separately rather than as one number.
"""

import contextlib
import shutil
from pathlib import Path

from fastapi import APIRouter

from .paths import DATA_DIR

router = APIRouter(prefix="/api/storage", tags=["storage"])

# name, folder, whether deleting it only costs time to rebuild
AREAS = [
    ("media", "media", False),
    ("projects", "projects", False),
    ("templates", "templates", False),
    ("proxies", "proxies", True),
    ("renders", "renders", True),
    ("thumbnails", "thumbs", True),
    ("waveforms", "peaks", True),
    ("filmstrips", "filmstrips", True),
    ("effect previews", "catalogue-previews", True),
    ("models", "models", True),
    ("speech runtime", "ai-runtime", True),
]


def _size(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    total = 0
    count = 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except OSError:
                continue
            count += 1
    return total, count


@router.get("")
def usage() -> dict:
    areas = []
    for label, folder, derived in AREAS:
        size, count = _size(DATA_DIR / folder)
        if size or count:
            areas.append({"label": label, "folder": folder, "bytes": size, "files": count, "derived": derived})
    free = 0
    with contextlib.suppress(OSError):
        free = shutil.disk_usage(DATA_DIR).free
    return {
        "root": str(DATA_DIR),
        "total": sum(area["bytes"] for area in areas),
        "reclaimable": sum(area["bytes"] for area in areas if area["derived"]),
        "free": free,
        "areas": sorted(areas, key=lambda area: -area["bytes"]),
    }
