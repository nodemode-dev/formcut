"""Preset store for formcut: named clip styles saved to a json index,
shareable as .fcpreset files (plain json). A style is an opaque dict of the
clip's non-timeline fields (transform, effect, key, mask, speed, fades,
audio fx, text style, transition); the engine applies it client-side, so
the store never interprets it beyond size and shape guards."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from .durable import read_json, write_json
from .media import DATA_DIR

router = APIRouter(prefix="/api/presets", tags=["presets"])

PRESETS_FILE = DATA_DIR / "presets.json"
_lock = threading.Lock()
MAX_STYLE_BYTES = 32_768
MAX_PRESETS = 200


def _read() -> list[dict]:
    return read_json(PRESETS_FILE, [])  # a damaged file set aside and its backup read, not the presets lost


def _write(items: list[dict]) -> None:
    write_json(PRESETS_FILE, items)


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

# Caption looks: finished caption styles built on the word styles (highlight,
# pop, box), the one-tap templates a CapCut user reaches for. Each is a
# TextStyle patch the Captions panel applies to a track and keeps for the
# next transcription; the thumbnail is drawn by the renderer with the second
# word lit, so the card shows the look in motion, not a still.
CAPTION_STYLES: list[dict] = [
    {
        "id": "karaoke",
        "name": "Karaoke",
        "style": {
            "size": 6,
            "color": "#ffffff",
            "bold": True,
            "weight": 800,
            "align": "center",
            "outlineColor": "#000000",
            "outlineWidth": 4,
            "lineHeight": 1.15,
            "wordStyle": {"mode": "highlight", "colour": "#ffd633"},
        },
    },
    {
        "id": "pop-word",
        "name": "Pop word",
        "style": {
            "size": 6,
            "color": "#ffffff",
            "bold": True,
            "weight": 800,
            "align": "center",
            "outlineColor": "#000000",
            "outlineWidth": 3,
            "shadowColor": "#000000",
            "shadowBlur": 6,
            "shadowY": 3,
            "wordStyle": {"mode": "pop", "colour": "#ff5a36"},
        },
    },
    {
        "id": "boxed",
        "name": "Boxed",
        "style": {
            "size": 6,
            "color": "#ffffff",
            "bold": True,
            "weight": 700,
            "align": "center",
            "outlineWidth": 0,
            "wordStyle": {"mode": "box", "colour": "#2f6fff"},
        },
    },
    {
        "id": "clean-plate",
        "name": "Clean plate",
        "style": {
            "size": 5,
            "color": "#f2f4f5",
            "bold": False,
            "weight": 500,
            "align": "center",
            "outlineWidth": 0,
            "plateColor": "#101416",
            "plateOpacity": 0.78,
            "platePadding": 14,
            "plateRadius": 6,
            "wordStyle": {"mode": "highlight", "colour": "#ffd633"},
        },
    },
    {
        "id": "neon",
        "name": "Neon",
        "style": {
            "size": 6,
            "color": "#e8fff9",
            "bold": True,
            "weight": 800,
            "align": "center",
            "outlineColor": "#00c2a8",
            "outlineWidth": 2,
            "shadowColor": "#00ffd0",
            "shadowBlur": 14,
            "shadowY": 0,
            "letterSpacing": 1,
            "wordStyle": {"mode": "highlight", "colour": "#ff3cac"},
        },
    },
    {
        "id": "bold-yellow",
        "name": "Bold yellow",
        "style": {
            "size": 7,
            "color": "#ffd633",
            "bold": True,
            "weight": 900,
            "align": "center",
            "outlineColor": "#000000",
            "outlineWidth": 5,
            "letterSpacing": -1,
            "wordStyle": {"mode": "pop", "colour": "#ffffff"},
        },
    },
    {
        "id": "quiet",
        "name": "Quiet",
        "style": {
            "size": 5,
            "color": "#f2f4f5",
            "bold": False,
            "weight": 400,
            "align": "center",
            "outlineWidth": 0,
            "shadowColor": "#000000",
            "shadowBlur": 8,
            "shadowY": 3,
            "lineHeight": 1.3,
            "wordStyle": {"mode": "highlight", "colour": "#ffffff"},
        },
    },
    {
        "id": "lower-plate",
        "name": "Lower plate",
        "style": {
            "size": 5,
            "color": "#ffffff",
            "bold": True,
            "weight": 700,
            "align": "left",
            "outlineWidth": 0,
            "plateColor": "#ff5a36",
            "plateOpacity": 0.92,
            "platePadding": 12,
            "plateRadius": 3,
            "wordStyle": {"mode": "box", "colour": "#101416"},
        },
    },
    # The animated looks (v2.0.3): the spoken word eases in, fading in as the words arrive ("reveal") or rising
    # into place ("rise"), over its first WORD_EASE seconds (renderer.py)
    {
        "id": "word-by-word",
        "name": "Word by word",
        "style": {
            "size": 6,
            "color": "#ffffff",
            "bold": True,
            "weight": 800,
            "align": "center",
            "outlineColor": "#000000",
            "outlineWidth": 4,
            "lineHeight": 1.15,
            "wordStyle": {"mode": "reveal", "colour": "#ffffff"},
        },
    },
    {
        "id": "reveal-gold",
        "name": "Gold reveal",
        "style": {
            "size": 6.5,
            "color": "#ffffff",
            "bold": True,
            "weight": 900,
            "align": "center",
            "outlineColor": "#000000",
            "outlineWidth": 5,
            "shadowColor": "#000000",
            "shadowBlur": 6,
            "shadowY": 2,
            "wordStyle": {"mode": "reveal", "colour": "#ffd633"},
        },
    },
    {
        "id": "reveal-plate",
        "name": "Plate reveal",
        "style": {
            "size": 5,
            "color": "#f2f4f5",
            "bold": False,
            "weight": 600,
            "align": "center",
            "outlineWidth": 0,
            "plateColor": "#101416",
            "plateOpacity": 0.78,
            "platePadding": 14,
            "plateRadius": 6,
            "wordStyle": {"mode": "reveal", "colour": "#7cf0ff"},
        },
    },
    {
        "id": "rise",
        "name": "Rise",
        "style": {
            "size": 6,
            "color": "#ffffff",
            "bold": True,
            "weight": 800,
            "align": "center",
            "outlineColor": "#001018",
            "outlineWidth": 4,
            "lineHeight": 1.2,
            "wordStyle": {"mode": "rise", "colour": "#7cf0ff"},
        },
    },
    {
        "id": "rise-sunset",
        "name": "Sunset rise",
        "style": {
            "size": 6.5,
            "color": "#fff4e8",
            "bold": True,
            "weight": 900,
            "align": "center",
            "outlineColor": "#1a0a00",
            "outlineWidth": 5,
            "lineHeight": 1.2,
            "wordStyle": {"mode": "rise", "colour": "#ff8a3d"},
        },
    },
    {
        "id": "rise-neon",
        "name": "Neon rise",
        "style": {
            "size": 6,
            "color": "#f4ffe8",
            "bold": True,
            "weight": 800,
            "align": "center",
            "outlineColor": "#0b0014",
            "outlineWidth": 3,
            "shadowColor": "#b6ff3b",
            "shadowBlur": 12,
            "shadowY": 0,
            "letterSpacing": 1,
            "wordStyle": {"mode": "rise", "colour": "#b6ff3b"},
        },
    },
]
CAPTION_STYLE_IDS = {entry["id"] for entry in CAPTION_STYLES}


def caption_style(look_id: str) -> dict | None:
    """A shipped look or a packaged one, by id."""
    found = next((e for e in CAPTION_STYLES if e["id"] == look_id), None)
    if found is not None:
        return found
    from .effect_packages import entries

    return next(({"id": e["id"], "name": e["name"], "style": e["style"]} for e in entries("captions") if e["id"] == look_id), None)


@router.get("/titles")
def list_title_styles() -> list[dict]:
    return TITLE_STYLES


@router.get("/captions")
def list_caption_styles() -> list[dict]:
    """The shipped looks, then every installed captions package as a look of its own."""
    from .effect_packages import entries

    packaged = [
        {"id": e["id"], "name": e["name"], "style": e["style"], "package": True}
        for e in entries("captions")
        if e["id"] not in CAPTION_STYLE_IDS
    ]
    return [*CAPTION_STYLES, *packaged]


class ShareBody(BaseModel):
    name: str
    style: dict
    author: str = ""


@router.post("/captions/share")
def share_caption_look(body: ShareBody) -> Response:
    """A caption look as a captions package: a zip of its manifest.json, made the way the community registry's own
    packages are (stored, one fixed date, the manifest's keys sorted), checked as the installer checks a package.
    Any formcut installs it as it is; listed in the registry (.docs/registry/README.md), anyone installs it from the
    effects browser's Community packages. The zip's SHA-256 comes back in X-Formcut-Sha256, for the registry entry."""
    from .effect_packages import load_package

    name = _clean_name(body.name) if body.name.strip() else "My caption look"
    author = re.sub(r"[^A-Za-z0-9_.-]", "", body.author.lstrip("@"))[:39]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "look"
    look_id = f"{slug}-by-{author.lower().replace('_', '-').replace('.', '-')}" if author else slug
    if len(look_id) < 2 or look_id in CAPTION_STYLE_IDS:
        look_id = f"{look_id}-look"
    manifest = {"id": look_id, "name": name, "kind": "captions", "author": author, "style": body.style}
    with tempfile.TemporaryDirectory() as folder:
        (Path(folder) / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        try:
            entry = load_package(Path(folder))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    manifest["style"] = entry["style"]
    data = package_zip(manifest)
    return Response(
        data,
        media_type="application/zip",
        headers={
            "content-disposition": f'attachment; filename="{look_id}.zip"',
            "x-formcut-sha256": hashlib.sha256(data).hexdigest(),
            "access-control-expose-headers": "content-disposition, x-formcut-sha256",
        },
    )


def package_zip(manifest: dict) -> bytes:
    """A package's zip as the registry's packages are made: manifest.json alone, stored, dated 2026-09-26, the
    keys sorted, so the same look always makes the same bytes and the same hash."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        info = zipfile.ZipInfo("manifest.json", date_time=(2026, 9, 26, 0, 0, 0))
        info.external_attr = 0o644 << 16
        archive.writestr(info, json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return buffer.getvalue()


@router.get("/texttemplates")
def list_text_templates() -> list[dict]:
    """Animated titles (text_templates.py), timed from where they are added."""
    from .text_templates import listing

    return listing()
