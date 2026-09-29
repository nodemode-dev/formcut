"""Projects as .fmc files on disk (v2.2.4), as After Effects keeps an .aep.

A project lived only in formcut's data folder. Now File > Save As writes it to a <title>.fmc wherever the person
chooses, and from then on every save of the project (the Save command and the autosave alike) writes the file too.
File > Open project file reads one back.

An .fmc is JSON: the format and its version, the app that wrote it, the project as the store holds it, and a media
table: for every media item a clip uses, its name, kind and length, the path of its file (for a linked item, the
file where it is; for one formcut copied in, that copy), the same path relative to the .fmc's folder (so a project
folder moved or handed over as a whole still finds its footage), its size, modification time and fingerprint.

Opening a file puts its project in the store (the file is the word on it) and brings its media back under the ids
its clips use: from the library when the file is there; else linked from the path the table gives; else from the
path relative to the .fmc; what is still not found is returned as missing, for Locate and Search a folder
(linking.py). The files a project is kept in are remembered (project-files.json, durable), with the recent ones.
"""

from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import linking, media, store
from .durable import read_json, write_json
from .paths import DATA_DIR

router = APIRouter(prefix="/api/project-files", tags=["projects"])
FORMAT = "formcut-project-file"
VERSION = 1
SUFFIX = ".fmc"
LINKS = DATA_DIR / "project-files.json"  # {"files": {project id: path}, "recent": [paths]}


def _links() -> dict:
    data = read_json(LINKS, {"files": {}, "recent": []})
    data.setdefault("files", {})
    data.setdefault("recent", [])
    return data


def _remember(project_id: str, path: Path) -> None:
    data = _links()
    data["files"][project_id] = str(path)
    data["recent"] = [str(path), *[p for p in data["recent"] if p != str(path)][:19]]
    write_json(LINKS, data)


def file_of(project_id: str) -> Path | None:
    path = _links()["files"].get(project_id)
    return Path(path) if path else None


def _media_ids(value) -> set[str]:
    found = set()
    if isinstance(value, dict):
        if isinstance(value.get("mediaId"), str):
            found.add(value["mediaId"])
        for child in value.values():
            found |= _media_ids(child)
    elif isinstance(value, list):
        for child in value:
            found |= _media_ids(child)
    return found


def media_table(project: dict, where: Path) -> dict:
    """What the project's clips use, and where each file is (also relative to the .fmc's folder)."""
    records = {item["id"]: item for item in media.list_media()}
    table = {}
    for media_id in sorted(_media_ids(project)):
        item = records.get(media_id)
        if item is None:
            continue
        file = media.media_path(media_id)
        path = Path(item["path"]) if item.get("path") else (file.resolve() if file else None)
        entry = {key: item.get(key) for key in ("name", "kind", "duration", "width", "height", "size", "mtime", "fingerprint")}
        entry["linked"] = bool(item.get("linked"))
        if path is not None:
            entry["path"] = str(path)
            with contextlib.suppress(ValueError):
                entry["relative"] = os.path.relpath(path, where.parent)
        if not entry.get("fingerprint") and file is not None:
            with contextlib.suppress(OSError):
                entry["fingerprint"] = linking.fingerprint(file)
        table[media_id] = {k: v for k, v in entry.items() if v is not None}
    return table


def write_file(project_id: str, path: Path) -> Path:
    from .main import APP_VERSION

    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    path = Path(path).expanduser()
    if path.suffix.lower() != SUFFIX:
        path = path.with_name(path.name + SUFFIX)
    document = {
        "format": FORMAT,
        "version": VERSION,
        "app": f"formcut {APP_VERSION}",
        "saved": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "project": project,
        "media": media_table(project, path),
    }
    write_json(path, document)
    _remember(project_id, path)
    return path


def after_save(project: dict) -> None:
    """A project kept in a file: the file follows each save (the Save command and the autosave alike)."""
    path = file_of(str(project.get("id")))
    if path is not None:
        with contextlib.suppress(OSError, HTTPException):
            write_file(str(project["id"]), path)


def open_file(path: Path) -> dict:
    path = Path(path).expanduser().resolve()
    try:
        document = read_json(path, None)
    except OSError as exc:
        raise HTTPException(404, f"could not read {path}: {exc}") from exc
    if not isinstance(document, dict) or document.get("format") != FORMAT or not isinstance(document.get("project"), dict):
        raise HTTPException(400, f"{path.name} is not a formcut project file")
    if int(document.get("version", 0)) > VERSION:
        raise HTTPException(400, f"{path.name} was written by a newer formcut ({document.get('app')}); update to open it")
    project = document["project"]
    if not project.get("id"):
        raise HTTPException(400, f"{path.name} holds no project id")
    existing = store.get_project(project["id"])
    project = {**project, "revision": int(existing.get("revision", 0)) if existing else 0}
    saved = store._save_project(project)  # the file is the word on it; the file itself is not written back yet
    missing, linked = [], []
    for media_id, entry in (document.get("media") or {}).items():
        if media.media_path(media_id) is not None:
            continue
        found = None
        for candidate in (entry.get("path"), entry.get("relative") and str(path.parent / entry["relative"])):
            if candidate and Path(candidate).is_file():
                found = Path(candidate)
                break
        if found is not None:
            with contextlib.suppress(HTTPException):
                linking.link_path(found, name=entry.get("name"), media_id=media_id)
                linked.append(media_id)
                continue
        missing.append({"id": media_id, **{k: entry.get(k) for k in ("name", "kind", "path", "duration")}})
        _keep_record(media_id, entry)
    _remember(saved["id"], path)
    return {"project": saved, "path": str(path), "linked": linked, "missing": missing}


def _keep_record(media_id: str, entry: dict) -> None:
    """A missing media item still named in the library, so its clips show what they want and it can be relinked."""
    with media._lock:
        items = media._read()
        if any(item.get("id") == media_id for item in items):
            return
        items.append(
            {
                "id": media_id,
                "thumb": False,
                "linked": True,
                "missingSince": time.time(),
                **{k: v for k, v in entry.items() if k != "relative"},
            }
        )
        media._write(items)


class SaveBody(BaseModel):
    projectId: str
    path: str | None = None


@router.post("/save")
def save_file(body: SaveBody) -> dict:
    """The project into its file: the path given (Save As), or the file it is already kept in."""
    path = Path(body.path) if body.path else file_of(body.projectId)
    if path is None:
        raise HTTPException(409, "choose where to save the project file first")
    return {"path": str(write_file(body.projectId, path))}


class OpenBody(BaseModel):
    path: str


@router.post("/open")
def open_project_file(body: OpenBody) -> dict:
    return open_file(Path(body.path))


@router.get("/recent")
def recent_files() -> list[dict]:
    return [{"path": p, "name": Path(p).stem, "there": Path(p).is_file()} for p in _links()["recent"]]


@router.get("/of/{project_id}")
def project_file(project_id: str) -> dict:
    path = file_of(project_id)
    return {"path": str(path) if path else None}
