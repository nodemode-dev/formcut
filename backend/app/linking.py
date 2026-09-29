"""Media linked where it is, and found again when it moves (v2.2.4), as After Effects does.

formcut copied every imported file into its own media folder (media/<id>.<ext>), so a project depended on formcut's
private copy and its index, and nothing knew where the footage had come from. A file imported from this computer is
now linked instead: media/<id>.<ext> is a symbolic link to the file where it is, so every part of the engine that
opens media/<id>.* (the renderer, exports, thumbnails, proxies, analysis) reads the original, untouched and uncopied.
The record keeps the file's path, size, modification time and a fingerprint (its size and a SHA-256 of its first and
last megabyte), which recognise it again under another name or in another folder. Deleting it from the library
removes the link only, never the file. (Where the system refuses a link, as Windows may without developer mode, the
file is copied as before, and the record says so.)

When a linked file moves or goes, its link dangles and the clip is reported missing (missing()). relink() points it at
the file where it is now, asking first when that file's kind or length differs; search() looks through a folder and
everything below it for every missing file at once, by name, then by size and fingerprint, and relinks each one found.

choose() opens the system's own file dialogs (the Mac's through osascript, zenity or kdialog on Linux, PowerShell on
Windows) for the engine running on this computer, which is how a path, not just a file's bytes, reaches formcut.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import media, proxies

router = APIRouter(tags=["media"])
MIB = 1 << 20


def fingerprint(path: Path) -> str:
    """The file's size and a SHA-256 of its first and last megabyte: quick on a large file, and enough to know it."""
    size = path.stat().st_size
    digest = hashlib.sha256(str(size).encode())
    with open(path, "rb") as handle:
        digest.update(handle.read(MIB))
        if size > 2 * MIB:
            handle.seek(size - MIB)
            digest.update(handle.read(MIB))
    return f"{size}:{digest.hexdigest()[:32]}"


def _place(media_id: str, target: Path) -> tuple[Path, bool]:
    """media/<id><ext> made a link to target (replacing any link or file of that id); a copy where links are refused."""
    media.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    for old in media.MEDIA_DIR.glob(f"{media_id}.*"):
        if old.is_symlink() or old.suffix.lower() != target.suffix.lower():
            old.unlink(missing_ok=True)
    place = media.MEDIA_DIR / f"{media_id}{target.suffix.lower()}"
    staged = media.MEDIA_DIR / f".link-{uuid.uuid4().hex}{target.suffix.lower()}"
    try:
        os.symlink(target, staged)
        os.replace(staged, place)
        return place, True
    except OSError:
        staged.unlink(missing_ok=True)
        shutil.copy2(target, place)
        return place, False


def _facts(path: Path) -> dict:
    stat = path.stat()
    return {"path": str(path), "mtime": stat.st_mtime, "fingerprint": fingerprint(path)}


def link_path(path: Path, name: str | None = None, media_id: str | None = None) -> dict:
    """A file on this computer into the library, linked where it is. The same file already linked is returned as it
    is; with media_id, that id is given the file (a project file's media, put back under the id its clips use)."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise HTTPException(404, f"no file at {path}")
    kind = media._kind(path.suffix.lower())
    if kind is None:
        raise HTTPException(415, f"unsupported file type {path.suffix or 'none'}")
    with media._lock:
        items = media._read()
    if media_id is None:
        same = next((i for i in items if i.get("path") == str(path) and i.get("size") == path.stat().st_size), None)
        if same is not None and media.media_path(same["id"]) is not None:
            return same
    media_id = media_id or uuid.uuid4().hex
    place, linked = _place(media_id, path)
    info = media._probe(place, kind)
    thumb = media.THUMB_DIR / f"{media_id}.jpg"
    has_thumb = thumb.is_file() or media._thumbnail(place, thumb, kind, info["duration"])
    item = {
        "id": media_id,
        "name": name or path.name,
        "kind": kind,
        "size": path.stat().st_size,
        "thumb": has_thumb,
        **info,
        **_facts(path),
        "linked": linked,
        **({} if linked else {"copied": True}),
    }
    with media._lock:
        items = [entry for entry in media._read() if entry.get("id") != media_id]
        items.append(item)
        media._write(items)
    if proxies.wants_proxy(item):
        proxies.enqueue(media_id, place)
    return item


def missing(ids: list[str] | None = None) -> list[dict]:
    """The library's media whose file is not there (a link whose file moved or went, or a file gone), with the path
    each was last at."""
    with media._lock:
        items = media._read()
    wanted = set(ids) if ids else None
    out = []
    for item in items:
        if wanted is not None and item["id"] not in wanted:
            continue
        if media.media_path(item["id"]) is None:
            out.append(
                {
                    "id": item["id"],
                    "name": item.get("name"),
                    "kind": item.get("kind"),
                    "path": item.get("path"),
                    "duration": item.get("duration"),
                }
            )
    return out


class Mismatch(Exception):
    pass


def relink(media_id: str, path: Path, force: bool = False) -> dict:
    """The media's link pointed at path. A file of another kind is refused; one of another length (more than half a
    second) is refused unless forced, as After Effects asks before replacing footage with a different clip."""
    item = media._find(media_id)
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise HTTPException(404, f"no file at {path}")
    kind = media._kind(path.suffix.lower())
    if kind != item.get("kind"):
        raise HTTPException(400, f"{path.name} is {kind or 'not a media file'}, and {item.get('name')} was {item.get('kind')}")
    probe = media._probe(path, kind)
    if not force and kind != "image" and abs(float(probe.get("duration") or 0) - float(item.get("duration") or 0)) > 0.5:
        raise Mismatch(
            f"{path.name} lasts {float(probe.get('duration') or 0):.1f} s, and {item.get('name')} lasted {float(item.get('duration') or 0):.1f} s"
        )
    same = item.get("fingerprint") == fingerprint(path)
    place, linked = _place(media_id, path)
    updated = {**item, **probe, **_facts(path), "size": path.stat().st_size, "linked": linked}
    updated.pop("copied", None)
    if not linked:
        updated["copied"] = True
    with media._lock:
        items = [updated if entry.get("id") == media_id else entry for entry in media._read()]
        media._write(items)
    # the preview forgets where the file was, and decoders of the old file are let go
    from .render_api import forget_media
    from .video_source import forget_path

    forget_media(media_id)
    forget_path(place)
    if not same:
        # another file under the same id: what was made from the old one goes
        (media.THUMB_DIR / f"{media_id}.jpg").unlink(missing_ok=True)
        updated["thumb"] = media._thumbnail(place, media.THUMB_DIR / f"{media_id}.jpg", kind, updated.get("duration", 0))
        proxies.remove(media_id)
    return updated


def search(folder: Path, ids: list[str] | None = None, limit: int = 200_000) -> dict:
    """Every missing file looked for in folder and below: by its name (the same size first), then, renamed, by its size
    and fingerprint. Each one found is relinked; what is left is returned. Hidden folders and packages are passed by."""
    folder = Path(folder).expanduser().resolve()
    if not folder.is_dir():
        raise HTTPException(404, f"no folder at {folder}")
    wanted = missing(ids)
    if not wanted:
        return {"relinked": [], "missing": []}
    by_name: dict[str, list[Path]] = {}
    by_size: dict[int, list[Path]] = {}
    seen = 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and not d.endswith((".app", ".photoslibrary", ".fcpbundle"))]
        for name in files:
            if name.startswith("."):
                continue
            path = Path(root) / name
            by_name.setdefault(name.lower(), []).append(path)
            try:
                by_size.setdefault(path.stat().st_size, []).append(path)
            except OSError:
                continue
            seen += 1
        if seen >= limit:
            break
    relinked, left = [], []
    records = {i["id"]: i for i in media.list_media()}
    for entry in wanted:
        item = records.get(entry["id"], {})
        name = Path(entry.get("path") or entry.get("name") or "").name.lower()
        size, mark = item.get("size"), item.get("fingerprint")
        found = None
        candidates = sorted(by_name.get(name, []), key=lambda p: p.stat().st_size != size)
        for path in candidates:
            if not mark or path.stat().st_size != size or fingerprint(path) == mark:
                found = path
                break
        if found is None and size and mark:
            found = next((p for p in by_size.get(size, []) if fingerprint(p) == mark), None)
        if found is None:
            left.append(entry)
            continue
        try:
            relinked.append({"id": entry["id"], "path": str(relink(entry["id"], found)["path"])})
        except (HTTPException, Mismatch) as exc:
            left.append({**entry, "problem": str(getattr(exc, "detail", exc))})
    return {"relinked": relinked, "missing": left, "looked": seen}


def choose(
    kind: str = "open", multiple: bool = False, title: str = "", default_name: str = "", types: list[str] | None = None
) -> list[str]:
    """The system's own dialog: files to open, a folder, or where to save. The paths chosen, none when cancelled."""
    system = platform.system()
    title = title or {"open": "Choose files", "folder": "Choose a folder", "save": "Save as"}.get(kind, "Choose")
    if system == "Darwin":
        quoted = title.replace('"', "'")
        if kind == "folder":
            script = f'POSIX path of (choose folder with prompt "{quoted}")'
        elif kind == "save":
            script = f'POSIX path of (choose file name with prompt "{quoted}" default name "{default_name.replace(chr(34), "")}")'
        else:
            of_type = f" of type {{{', '.join(chr(34) + t.lstrip('.') + chr(34) for t in types)}}}" if types else ""
            many = " with multiple selections allowed" if multiple else ""
            script = (
                f'set chosen to choose file with prompt "{quoted}"{of_type}{many}\n'
                'if class of chosen is list then\nset out to ""\nrepeat with f in chosen\nset out to out & POSIX path of f & linefeed\nend repeat\nreturn out\n'
                "else\nreturn POSIX path of chosen\nend if"
            )
        done = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, check=False)
    elif system == "Linux" and shutil.which("zenity"):
        command = ["zenity", "--file-selection", f"--title={title}"]
        if kind == "folder":
            command.append("--directory")
        elif kind == "save":
            command += ["--save", "--confirm-overwrite", f"--filename={default_name}"]
        elif multiple:
            command += ["--multiple", "--separator=\n"]
        done = subprocess.run(command, capture_output=True, text=True, check=False)
    elif system == "Linux" and shutil.which("kdialog"):
        mode = {"folder": "--getexistingdirectory", "save": "--getsavefilename"}.get(kind, "--getopenfilename")
        command = ["kdialog", mode, str(Path.home() / default_name if kind == "save" else Path.home())]
        if kind == "open" and multiple:
            command += ["--multiple", "--separate-output"]
        done = subprocess.run(command, capture_output=True, text=True, check=False)
    elif system == "Windows":
        if kind == "folder":
            body = "$d = New-Object System.Windows.Forms.FolderBrowserDialog; if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"
        elif kind == "save":
            body = f"$d = New-Object System.Windows.Forms.SaveFileDialog; $d.FileName = '{default_name}'; if ($d.ShowDialog() -eq 'OK') {{ $d.FileName }}"
        else:
            body = f"$d = New-Object System.Windows.Forms.OpenFileDialog; $d.Multiselect = ${'true' if multiple else 'false'}; if ($d.ShowDialog() -eq 'OK') {{ $d.FileNames -join \"`n\" }}"
        done = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Add-Type -AssemblyName System.Windows.Forms; " + body],
            capture_output=True,
            text=True,
            check=False,
        )
    else:
        raise HTTPException(501, "no file dialog on this system: install zenity or kdialog, or import through the browser")
    if done.returncode != 0:
        return []  # cancelled
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def dialogs_available() -> bool:
    system = platform.system()
    return system in ("Darwin", "Windows") or (system == "Linux" and bool(shutil.which("zenity") or shutil.which("kdialog")))


class LinkBody(BaseModel):
    paths: list[str]


@router.post("/api/media/link", status_code=201)
def link_files(body: LinkBody) -> list[dict]:
    """Files on this computer into the library, linked where they are (not copied)."""
    return [link_path(Path(path)) for path in body.paths]


@router.get("/api/media/missing")
def list_missing(ids: str = "") -> list[dict]:
    return missing([i for i in ids.split(",") if i] or None)


class RelinkBody(BaseModel):
    path: str
    force: bool = False


@router.post("/api/media/{media_id}/relink")
def relink_media(media_id: str, body: RelinkBody) -> dict:
    try:
        return relink(media_id, Path(body.path), body.force)
    except Mismatch as exc:
        raise HTTPException(409, str(exc)) from exc


class SearchBody(BaseModel):
    folder: str
    ids: list[str] | None = None


@router.post("/api/media/relink-search")
def relink_search(body: SearchBody) -> dict:
    started = time.time()
    found = search(Path(body.folder), body.ids)
    return {**found, "seconds": round(time.time() - started, 1)}


class ChooseBody(BaseModel):
    kind: str = "open"
    multiple: bool = False
    title: str = ""
    defaultName: str = ""
    types: list[str] | None = None


@router.get("/api/system/dialogs")
def system_dialogs() -> dict:
    return {"available": dialogs_available()}


@router.post("/api/system/choose")
def system_choose(body: ChooseBody) -> dict:
    """The system's own file dialog, on this computer (the engine's): the paths chosen, or none when cancelled."""
    return {"paths": choose(body.kind, body.multiple, body.title, body.defaultName, body.types)}
