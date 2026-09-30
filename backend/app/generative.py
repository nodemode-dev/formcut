"""The generative library (v2.3.0): what the image and video generator makes, kept apart from the media library.

The owner: generations should not live in media.json. They are kept here instead: each file in generative/, its
thumbnail in generative-thumbs/, its record (prompt, seed, steps, size, LoRAs, model, the time it took) in
generative.json, written the durable way (durable.py). The Studio's results show this library; a generation goes into
the media library, for the timeline, only when asked (Add to media: a copy imported there, the generative one kept).
Audio the generator makes (speech, music) still goes straight to the media library, as it is laid on the timeline at
once.
"""

from __future__ import annotations

import shutil
import threading
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .durable import read_json, write_json
from .paths import DATA_DIR

router = APIRouter(prefix="/api/generative", tags=["generate"])
FOLDER = DATA_DIR / "generative"
THUMBS = DATA_DIR / "generative-thumbs"
INDEX = DATA_DIR / "generative.json"
THUMB_SIZE = 512  # the long side: tiles are shown large
_lock = threading.Lock()


def _read() -> list[dict]:
    items = read_json(INDEX, [])
    return items if isinstance(items, list) else []


def _thumbnail(path: Path, kind: str, target: Path) -> bool:
    try:
        if kind == "image":
            from PIL import Image

            with Image.open(path) as picture:
                picture.thumbnail((THUMB_SIZE, THUMB_SIZE))
                picture.convert("RGB").save(target, "JPEG", quality=88)
            return True
        from . import media

        return bool(media._thumbnail(path, target, kind, 0.0))
    except Exception:  # noqa: BLE001 - a picture without a thumbnail is still kept
        return False


def add(source: Path, name: str, kind: str, extra: dict | None = None) -> dict:
    """A file the generator made, moved into the generative library with its thumbnail and record."""
    item_id = uuid.uuid4().hex
    FOLDER.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)
    stored = FOLDER / f"{item_id}{source.suffix.lower() or '.png'}"
    shutil.move(str(source), stored)
    thumb = _thumbnail(stored, kind, THUMBS / f"{item_id}.jpg")
    width = height = None
    if kind == "image":
        try:
            from PIL import Image

            with Image.open(stored) as picture:
                width, height = picture.size
        except OSError:
            pass
    item = {
        "id": item_id,
        "name": name,
        "kind": kind,
        "file": stored.name,
        "bytes": stored.stat().st_size,
        "thumb": thumb,
        "created": time.time(),
        **({"width": width, "height": height} if width else {}),
        **(extra or {}),
    }
    with _lock:
        items = _read()
        items.append(item)
        write_json(INDEX, items)
    return item


def find(item_id: str) -> dict:
    item = next((i for i in _read() if i.get("id") == item_id), None)
    if item is None:
        raise HTTPException(404, "no such generation")
    return item


def path_of(item: dict) -> Path:
    path = FOLDER / str(item.get("file") or "")
    if not path.is_file():
        raise HTTPException(404, "its file is missing")
    return path


@router.get("")
def list_generations(kind: str = "", limit: int = 120, before: float = 0.0) -> dict:
    """The latest first; before= a time pages back through older ones."""
    items = [i for i in _read() if (not kind or i.get("kind") == kind) and (not before or i.get("created", 0) < before)]
    items.sort(key=lambda i: i.get("created", 0), reverse=True)
    page = items[: max(1, min(500, limit))]
    return {"items": page, "more": len(items) > len(page)}


@router.get("/{item_id}/file")
def generation_file(item_id: str) -> FileResponse:
    item = find(item_id)
    return FileResponse(path_of(item), filename=f"{item.get('name', item_id)[:60]}{Path(item['file']).suffix}")


@router.get("/{item_id}/thumb")
def generation_thumb(item_id: str) -> FileResponse:
    item = find(item_id)
    thumb = THUMBS / f"{item_id}.jpg"
    if not thumb.is_file() and not _thumbnail(path_of(item), item.get("kind", "image"), thumb):
        raise HTTPException(404, "no thumbnail")
    return FileResponse(thumb, media_type="image/jpeg")


@router.delete("/{item_id}")
def delete_generation(item_id: str) -> dict:
    with _lock:
        items = _read()
        item = next((i for i in items if i.get("id") == item_id), None)
        if item is None:
            raise HTTPException(404, "no such generation")
        write_json(INDEX, [i for i in items if i.get("id") != item_id])
    (FOLDER / str(item.get("file") or "")).unlink(missing_ok=True)
    (THUMBS / f"{item_id}.jpg").unlink(missing_ok=True)
    return {"deleted": item_id}


@router.post("/{item_id}/to-media", status_code=201)
def add_to_media(item_id: str) -> dict:
    """A copy of the generation in the media library, for the timeline; the generation itself stays here."""
    from .media import ingest_path

    item = find(item_id)
    source = path_of(item)
    staged = FOLDER / f".to-media-{uuid.uuid4().hex}{source.suffix}"
    shutil.copy2(source, staged)
    keep = {
        k: item[k] for k in ("prompt", "seed", "steps", "loras", "sampler", "guidance", "parameters", "generator", "provider") if k in item
    }
    return ingest_path(staged, item.get("name") or source.name, extra={"source": "generated", "generative": item_id, **keep})
