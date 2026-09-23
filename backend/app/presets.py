"""Preset store for formcut: named clip styles saved to a json index,
shareable as .fcpreset files (plain json). A style is an opaque dict of the
clip's non-timeline fields (transform, effect, key, mask, speed, fades,
audio fx, text style, transition); the engine applies it client-side, so
the store never interprets it beyond size and shape guards."""

from __future__ import annotations

import base64
import json
import threading
import time
import uuid
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
    font: str | None = None  # base64 font bytes travelling with the preset


@router.get("")
def list_presets() -> list[dict]:
    with _lock:
        return _read()


@router.post("", status_code=201)
def save_preset(body: PresetBody) -> dict:
    style = _validate_style(body.style)
    if body.font:
        # TI4: the preset carries its font; install once, keyed by content hash
        from .fonts import install_font

        installed = install_font(base64.b64decode(body.font))
        style = {**style, "fontId": installed["id"]}
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


# TI3: the ten built-in title styles. Each is a full TextStyle the gallery applies
# in one click; thumbnails come from the engine so the card matches the render.
TITLE_STYLES: list[dict] = [
    {
        "id": "headline",
        "name": "Headline",
        "style": {
            "size": 11,
            "color": "#ffffff",
            "bold": True,
            "align": "center",
            "weight": 800,
            "outlineColor": "#000000",
            "outlineWidth": 4,
            "letterSpacing": -2,
            "lineHeight": 1.05,
        },
    },
    {
        "id": "subtitle",
        "name": "Subtitle",
        "style": {
            "size": 6,
            "color": "#f2f4f5",
            "bold": False,
            "align": "center",
            "weight": 400,
            "outlineWidth": 0,
            "shadowColor": "#000000",
            "shadowBlur": 8,
            "shadowY": 3,
            "lineHeight": 1.3,
        },
    },
    {
        "id": "lower-third",
        "name": "Lower third",
        "style": {
            "size": 6,
            "color": "#ffffff",
            "bold": True,
            "align": "left",
            "weight": 700,
            "outlineWidth": 0,
            "plateColor": "#101416",
            "plateOpacity": 0.78,
            "platePadding": 18,
            "plateRadius": 6,
            "letterSpacing": 2,
        },
    },
    {
        "id": "caption",
        "name": "Caption",
        "style": {
            "size": 5,
            "color": "#ffffff",
            "bold": True,
            "align": "center",
            "weight": 600,
            "outlineColor": "#000000",
            "outlineWidth": 3,
            "wrapWidth": 80,
            "lineHeight": 1.2,
        },
    },
    {
        "id": "outline",
        "name": "Outline",
        "style": {
            "size": 10,
            "color": "#00000000",
            "bold": True,
            "align": "center",
            "weight": 800,
            "outlineColor": "#ffffff",
            "outlineWidth": 5,
            "textOpacity": 1,
        },
    },
    {
        "id": "glow",
        "name": "Glow",
        "style": {
            "size": 10,
            "color": "#ffffff",
            "bold": True,
            "align": "center",
            "weight": 700,
            "outlineWidth": 0,
            "shadowColor": "#35d0ff",
            "shadowBlur": 22,
            "letterSpacing": 1,
        },
    },
    {
        "id": "serif",
        "name": "Serif",
        "style": {
            "size": 9,
            "color": "#f6efe2",
            "bold": False,
            "align": "center",
            "weight": 400,
            "italic": True,
            "outlineWidth": 0,
            "shadowColor": "#000000",
            "shadowBlur": 6,
            "letterSpacing": 4,
            "lineHeight": 1.35,
        },
    },
    {
        "id": "bold-pop",
        "name": "Bold pop",
        "style": {
            "size": 12,
            "color": "#ffe600",
            "bold": True,
            "align": "center",
            "weight": 900,
            "outlineColor": "#1a1a1a",
            "outlineWidth": 6,
            "shadowColor": "#1a1a1a",
            "shadowBlur": 0,
            "shadowX": 6,
            "shadowY": 6,
            "letterSpacing": -1,
        },
    },
    {
        "id": "boxed",
        "name": "Boxed",
        "style": {
            "size": 7,
            "color": "#101416",
            "bold": True,
            "align": "center",
            "weight": 700,
            "outlineWidth": 0,
            "plateColor": "#ffffff",
            "plateOpacity": 0.95,
            "platePadding": 22,
            "plateRadius": 26,
            "letterSpacing": 3,
        },
    },
    {
        "id": "minimal",
        "name": "Minimal",
        "style": {
            "size": 6,
            "color": "#ffffff",
            "bold": False,
            "align": "center",
            "weight": 300,
            "outlineWidth": 0,
            "letterSpacing": 12,
            "textOpacity": 0.92,
        },
    },
]

TITLE_STYLE_IDS = {entry["id"] for entry in TITLE_STYLES}


@router.get("/titles")
def list_title_styles() -> list[dict]:
    return TITLE_STYLES


@router.get("/texttemplates")
def list_text_templates() -> list[dict]:
    """Animated titles (text_templates.py), timed from where they are added."""
    from .text_templates import listing

    return listing()
