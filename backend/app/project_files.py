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
import platform
import shutil
import subprocess
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


def collect(project_id: str, folder: Path, report=lambda *_: None, cancelled=lambda: False) -> dict:
    """Collect Files, as After Effects does: <folder>/<title>/<title>.fmc with a copy of every file its clips use in
    Footage/ beside it, the .fmc pointing at those copies (by path and relative to it), so the folder can be moved,
    zipped or handed over whole. The project itself stays kept where it was; the collected .fmc is a copy of it.
    Two files of the same name are told apart (a number added); a file missing now is listed, not copied."""
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(404, "project not found")
    title = "".join(ch for ch in str(project.get("title") or "Untitled") if ch not in '/\\:*?"<>|').strip() or "Untitled"
    root = Path(folder).expanduser() / title
    footage = root / "Footage"
    footage.mkdir(parents=True, exist_ok=True)
    where = root / f"{title}{SUFFIX}"
    table = media_table(project, where)
    used: set[str] = set()
    missing, copied, total = [], 0, 0
    items = list(table.items())
    for index, (media_id, entry) in enumerate(items):
        if cancelled():
            raise InterruptedError("cancelled")
        source = media.media_path(media_id)
        if source is None:
            missing.append(entry.get("name") or media_id)
            continue
        name = Path(entry.get("path") or entry.get("name") or source.name).name
        stem, suffix = Path(name).stem, Path(name).suffix or source.suffix
        candidate, number = f"{stem}{suffix}", 2
        while candidate.lower() in used:
            candidate, number = f"{stem} {number}{suffix}", number + 1
        used.add(candidate.lower())
        target = footage / candidate
        report(index / max(1, len(items)), f"Copying {candidate}")
        shutil.copy2(source.resolve(), target)
        copied += 1
        total += target.stat().st_size
        entry.update({"path": str(target.resolve()), "relative": f"Footage/{candidate}", "linked": True})
    document = {
        "format": FORMAT,
        "version": VERSION,
        "app": f"formcut {_app_version()}",
        "saved": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "collected": True,
        "project": project,
        "media": table,
    }
    write_json(where, document, keep_backup=False)
    return {"path": str(where), "folder": str(root), "files": copied, "bytes": total, "missing": missing}


def _app_version() -> str:
    from .main import APP_VERSION

    return APP_VERSION


def reveal(path: Path) -> dict:
    """The file shown in the system's file manager (the Mac's Finder selects it)."""
    path = Path(path).expanduser()
    if not path.exists():
        raise HTTPException(404, f"nothing at {path}")
    system = platform.system()
    command = (
        ["open", "-R", str(path)]
        if system == "Darwin"
        else ["explorer", f"/select,{path}"]
        if system == "Windows"
        else ["xdg-open", str(path.parent)]
    )
    try:
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {"opened": False, "path": str(path), "detail": str(exc)}
    return {"opened": True, "path": str(path)}


class CollectBody(BaseModel):
    projectId: str
    folder: str


@router.post("/collect", status_code=202)
def collect_files(body: CollectBody) -> dict:
    from . import jobs

    return jobs.submit("collect", lambda _job, report, cancelled: collect(body.projectId, Path(body.folder), report, cancelled))


class RevealBody(BaseModel):
    path: str


@router.post("/reveal")
def reveal_file(body: RevealBody) -> dict:
    return reveal(Path(body.path))


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
