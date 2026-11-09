import os
import shutil
import sys
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .media import MEDIA_DIR, _lock, _read, ingest_path

router = APIRouter(prefix="/api/demo", tags=["demo"])
FILES = ["input-clip-example.mp4", "model-drop-MV.mp4", "a-sample.wav", "effect-example-image.jpg"]
_seeding = threading.Lock()


def demo_dir() -> Path:
    configured = os.environ.get("FORMCUT_DEMO_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "examples" / "demo"
    if getattr(sys, "frozen", False) and bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parents[2] / "examples" / "demo"


def _stored(item: dict) -> bool:
    """The demo item's file there and whole (the same size as the demo's own file), not merely a name that matches."""
    from .media import media_path

    path = media_path(item["id"])
    source = demo_dir() / str(item.get("name") or "")
    return path is not None and path.stat().st_size > 0 and (not source.is_file() or path.stat().st_size == source.stat().st_size)


REPO_DEMOS = ("edit", "grade", "deliver")


def repo_demo_dir(demo_id: str) -> Path:
    """The repository demos' media, shipped in the built interface (frontend/public/demos/<id>, copied by Vite)."""
    folders = [Path(__file__).resolve().parents[2] / "frontend" / "public" / "demos" / demo_id]
    if os.environ.get("FORMCUT_DIST"):
        folders.insert(0, Path(os.environ["FORMCUT_DIST"]) / "demos" / demo_id)
    if getattr(sys, "frozen", False):
        folders.insert(0, Path(getattr(sys, "_MEIPASS", "")) / "frontend_dist" / "demos" / demo_id)
    return next((folder for folder in folders if (folder / "manifest.json").is_file()), folders[-1])


@router.post("/{demo_id}")
def seed_repo_demo(demo_id: str) -> dict:
    """One of the repository demos (edit, grade, deliver) into the library, each file once, keyed by its media id."""
    import json

    if demo_id not in REPO_DEMOS:
        raise HTTPException(404, f"No demo called {demo_id}")
    folder = repo_demo_dir(demo_id)
    manifest = folder / "manifest.json"
    if not manifest.is_file():
        raise HTTPException(404, f"The {demo_id} demo's media is not included in this build")
    items = json.loads(manifest.read_text(encoding="utf-8"))["items"]
    with _seeding:
        with _lock:
            known = {}
            for item in _read():
                if item.get("source") == f"demo:{demo_id}" and item.get("name") not in known:
                    known[item["name"]] = item
        media = {}
        for entry in items:
            from .media import media_path

            item = known.get(entry["file"])
            path = media_path(item["id"]) if item else None
            if item and path is not None and path.stat().st_size == (folder / entry["file"]).stat().st_size:
                media[entry["id"]] = item
                continue
            MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            staged = MEDIA_DIR / f"upload_{uuid.uuid4().hex}{Path(entry['file']).suffix.lower()}"
            try:
                shutil.copyfile(folder / entry["file"], staged)
                media[entry["id"]] = ingest_path(staged, entry["file"], extra={"source": f"demo:{demo_id}"})
            finally:
                staged.unlink(missing_ok=True)
    return {"media": media}


@router.get("")
def demo_status() -> dict:
    folder = demo_dir()
    return {"available": all((folder / name).is_file() for name in FILES), "files": FILES}


@router.post("")
def seed_demo() -> dict:
    folder = demo_dir()
    missing = [name for name in FILES if not (folder / name).is_file()]
    if missing:
        raise HTTPException(404, "Demo media is not included in this build: " + ", ".join(missing))
    with _seeding:
        with _lock:
            # each demo file's first whole copy in the library (a lost index can leave several under one name)
            known = {}
            for item in _read():
                if item.get("source") == "demo" and item.get("name") not in known and _stored(item):
                    known[item["name"]] = item
        media = []
        for name in FILES:
            item = known.get(name)
            if item and _stored(item):
                media.append(item)
                continue
            MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            staged = MEDIA_DIR / f"upload_{uuid.uuid4().hex}{Path(name).suffix.lower()}"
            try:
                shutil.copyfile(folder / name, staged)
                media.append(ingest_path(staged, name, extra={"source": "demo"}))
            finally:
                staged.unlink(missing_ok=True)
    return {"media": media}
