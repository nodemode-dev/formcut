"""A project as one file: the .fc package.

A .fc is a zip. manifest.json names the format and the app that wrote it,
project.json is the document as the store holds it, assets.json carries the
fonts, LUTs and shaders the clips name (the same records a template carries),
and media/ holds every media file a clip references, stored rather than
compressed because the codecs already did that. Export streams the zip to a
file on disk and hands it over as a download, so a project with gigabytes of
footage never sits in memory; import spools the upload, ingests each media
file under a new id, restores the assets, rewrites every reference and saves
the project under a new id, so a dropped package never overwrites anything.
"""

import base64
import io
import json
import tempfile
import threading
import time
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from . import store
from .assets import ShaderInput, asset_path, upload_lut, upload_shader
from .fonts import upload_font
from .media import MEDIA_DIR, _read, ingest_path
from .paths import DATA_DIR
from .render_document import validate_document

router = APIRouter(prefix="/api/projects", tags=["projects"])
FORMAT = "formcut-project"
FORMAT_VERSION = 1
EXPORTS = DATA_DIR / "exports"
_lock = threading.RLock()
ASSET_FIELDS = (("lutId", ".cube"), ("shaderId", ".wgsl"))


def _clips(document: dict):
    for timeline in document.get("timelines") or []:
        for track in timeline.get("tracks") or []:
            yield from track.get("clips") or []


def _safe_name(title: str) -> str:
    kept = "".join(ch if ch.isalnum() or ch in " -_." else "-" for ch in title).strip(" .")
    return (kept or "project")[:80]


def gather_assets(document: dict) -> dict:
    """The fonts, LUTs and shaders the clips name, as text records (fonts base64)."""
    found = {}
    for clip in _clips(document):
        for holder, field, suffix in [
            (clip, "lutId", ".cube"),
            (clip, "shaderId", ".wgsl"),
            (clip.get("textStyle") or {}, "fontId", ".font"),
        ]:
            key = holder.get(field)
            if key and key not in found:
                path = asset_path(key, suffix)
                if not path.is_file():
                    continue
                found[key] = {
                    "type": field,
                    "source": base64.b64encode(path.read_bytes()).decode() if suffix == ".font" else path.read_text(),
                }
    return found


def build(project_id: str) -> Path:
    """Write the package for a stored project to the exports folder and return its path."""
    record = store.get_project(project_id)
    if record is None:
        raise HTTPException(404, "project not found")
    document = {k: v for k, v in record.items() if k != "id"}
    library = {item["id"]: item for item in _read()}
    media_index = {}
    files = []
    for clip in _clips(document):
        media_id = clip.get("mediaId")
        if not media_id or media_id in media_index:
            continue
        matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
        if not matches:
            continue
        item = library.get(media_id) or {}
        media_index[media_id] = {
            "name": item.get("name") or clip.get("label") or media_id,
            "suffix": matches[0].suffix,
            "kind": item.get("kind"),
        }
        files.append((media_id, matches[0]))
    EXPORTS.mkdir(parents=True, exist_ok=True)
    path = EXPORTS / f"{uuid.uuid4().hex}.fc"
    from .main import APP_VERSION  # main mounts this router, so it is read when a package is built

    manifest = {
        "format": FORMAT,
        "formatVersion": FORMAT_VERSION,
        "app": APP_VERSION,
        "title": record.get("title") or "",
        "exported": time.time(),
        "media": len(files),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr("project.json", json.dumps(document))
        archive.writestr("assets.json", json.dumps(gather_assets(document)))
        archive.writestr("media/index.json", json.dumps(media_index))
        for media_id, source in files:
            archive.write(source, f"media/{media_id}{source.suffix}", compress_type=zipfile.ZIP_STORED)
    return path


@router.get("/{project_id}/package")
def export_package(project_id: str):
    path = build(project_id)
    record = store.get_project(project_id) or {}
    name = _safe_name(str(record.get("title") or "project")) + ".fc"
    return FileResponse(
        path,
        media_type="application/x-formcut-project",
        filename=name,
        background=BackgroundTask(lambda: path.unlink(missing_ok=True)),
    )


def _restore_assets(assets: dict) -> dict:
    replacements = {}
    if not isinstance(assets, dict) or len(assets) > 256:
        raise ValueError("Invalid package assets")
    for key, asset in assets.items():
        source = asset.get("source")
        if not isinstance(source, str):
            raise ValueError("Asset source must be text")
        if asset.get("type") == "fontId":
            result = upload_font(UploadFile(filename="Package font.ttf", file=io.BytesIO(base64.b64decode(source, validate=True))))
        elif asset.get("type") == "lutId":
            result = upload_lut(UploadFile(filename="Package color.cube", file=io.BytesIO(source.encode())))
        elif asset.get("type") == "shaderId":
            result = upload_shader(ShaderInput(name="Package shader", source=source))
        else:
            raise ValueError("Unknown package asset")
        replacements[key] = result["id"]
    return replacements


def unpack(path: Path) -> dict:
    """Ingest a package's media and assets, rewrite the document, save it as a new project."""
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValueError("Not a formcut project package") from exc
    with archive:
        names = set(archive.namelist())
        if "manifest.json" not in names or "project.json" not in names:
            raise ValueError("Not a formcut project package")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("format") != FORMAT:
            raise ValueError("Not a formcut project package")
        if int(manifest.get("formatVersion", 0)) > FORMAT_VERSION:
            raise ValueError(f"This package was written by a newer formcut (format {manifest.get('formatVersion')})")
        document = json.loads(archive.read("project.json"))
        assets = json.loads(archive.read("assets.json")) if "assets.json" in names else {}
        media_index = json.loads(archive.read("media/index.json")) if "media/index.json" in names else {}
        if not isinstance(document, dict) or not isinstance(media_index, dict):
            raise ValueError("Malformed package")
        replacements = _restore_assets(assets)
        # Media: each file is staged beside the library and ingested under a new
        # id, so a package never clobbers a file the library already holds.
        for name in sorted(names):
            if not name.startswith("media/") or name == "media/index.json" or name.endswith("/"):
                continue
            stem = Path(name).name
            old_id = stem.split(".", 1)[0]
            if "/" in stem or ".." in stem:
                raise ValueError("Malformed package")
            meta = media_index.get(old_id, {})
            staged = MEDIA_DIR.parent / ("package-" + uuid.uuid4().hex + Path(stem).suffix.lower())
            staged.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as src, staged.open("wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
            try:
                result = ingest_path(staged, str(meta.get("name") or stem), extra={"source": "package"})
            finally:
                staged.unlink(missing_ok=True)
            replacements[old_id] = result["id"]
    for clip in _clips(document):
        for holder, field in [(clip, "lutId"), (clip, "shaderId"), (clip, "mediaId"), (clip.get("textStyle") or {}, "fontId")]:
            if holder.get(field) in replacements:
                holder[field] = replacements[holder[field]]
    validate_document({k: v for k, v in document.items() if k != "revision"})
    title = str(document.get("title") or manifest.get("title") or "Imported project")
    record = {
        "id": uuid.uuid4().hex,
        "title": title,
        "width": int(document.get("width", 1080)),
        "height": int(document.get("height", 1920)),
        "fps": int(document.get("fps", 30)),
        "timelines": document.get("timelines") or [],
        "activeTimeline": int(document.get("activeTimeline", 0)),
        "revision": 0,
    }
    with _lock:
        saved = store.save_project(record)
    return {"id": saved["id"], "title": saved.get("title"), "media": len([k for k in replacements if k in media_index])}


@router.post("/import", status_code=201)
def import_package(file: UploadFile) -> dict:
    """A dropped .fc: spooled to disk, unpacked, saved as a new project."""
    EXPORTS.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=EXPORTS, suffix=".fc", delete=False) as spool:
        staged = Path(spool.name)
        total = 0
        while True:
            chunk = file.file.read(1 << 20)
            if not chunk:
                break
            total += len(chunk)
            if total > 8_000_000_000:
                staged.unlink(missing_ok=True)
                raise HTTPException(413, "Package exceeds 8 GB")
            spool.write(chunk)
    try:
        return unpack(staged)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        staged.unlink(missing_ok=True)
