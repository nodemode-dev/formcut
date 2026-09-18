"""Preset store for formcut: named clip styles saved to a json index,
shareable as .fcpreset files (plain json). A style is an opaque dict of the
clip's non-timeline fields (transform, effect, key, mask, speed, fades,
audio fx, text style, transition); the engine applies it client-side, so
the store never interprets it beyond size and shape guards."""
from __future__ import annotations

import json
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .media import DATA_DIR

router = APIRouter(prefix="/api/presets", tags=["presets"])

PRESETS_FILE = DATA_DIR / "presets.json"
_lock = threading.Lock()
MAX_STYLE_BYTES = 32_768
MAX_PRESETS = 200


def _read() -> list[dict]:
    if not PRESETS_FILE.exists():
        return []
    try:
        return json.loads(PRESETS_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return []


def _write(items: list[dict]) -> None:
    PRESETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRESETS_FILE.write_text(json.dumps(items, indent=2))


def _clean_name(name: str) -> str:
    cleaned = "".join(ch for ch in name if ch.isalnum() or ch in " -_.").strip()
    return cleaned[:60] or "Preset"


def _validate_style(style: Any) -> dict:
    if not isinstance(style, dict) or not style:
        raise HTTPException(status_code=422, detail="style must be a non-empty object")
    raw = json.dumps(style)
    if len(raw) > MAX_STYLE_BYTES:
        raise HTTPException(status_code=413, detail="style too large")
    return style


class PresetBody(BaseModel):
    name: str
    style: dict


@router.get("")
def list_presets() -> list[dict]:
    with _lock:
        return _read()


@router.post("", status_code=201)
def save_preset(body: PresetBody) -> dict:
    style = _validate_style(body.style)
    item = {
        "id": uuid.uuid4().hex,
        "name": _clean_name(body.name),
        "style": style,
        "created": int(time.time()),
    }
    with _lock:
        items = _read()
        if len(items) >= MAX_PRESETS:
            raise HTTPException(status_code=409, detail="preset limit reached")
        items.append(item)
        _write(items)
    return item


@router.delete("/{preset_id}", status_code=204)
def delete_preset(preset_id: str):
    with _lock:
        items = _read()
        remaining = [p for p in items if p["id"] != preset_id]
        if len(remaining) == len(items):
            raise HTTPException(status_code=404, detail="unknown preset")
        _write(remaining)


@router.get("/{preset_id}/file")
def export_preset(preset_id: str) -> Response:
    with _lock:
        items = _read()
    for p in items:
        if p["id"] == preset_id:
            payload = json.dumps({"formcut_preset": 1, "name": p["name"], "style": p["style"]}, indent=2)
            fname = f"{p['name'].replace(' ', '_')}.fcpreset"
            return Response(
                content=payload,
                media_type="application/json",
                headers={"Content-Disposition": f'attachment; filename="{fname}"'},
            )
    raise HTTPException(status_code=404, detail="unknown preset")


@router.post("/import", status_code=201)
def import_preset(file: UploadFile) -> dict:
    try:
        data = json.loads(file.file.read(MAX_STYLE_BYTES + 4096))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=422, detail="not a valid preset file")
    if not isinstance(data, dict) or data.get("formcut_preset") != 1:
        raise HTTPException(status_code=422, detail="not a formcut preset")
    style = _validate_style(data.get("style"))
    return save_preset(PresetBody(name=str(data.get("name", "Imported")), style=style))
