"""Extensions under the Form Extension Contract, API 1: discovery, safe file serving and the window bridge.

The resolver and the file checks are the contract kit's (formext_host.py, vendored unchanged). This module adds the
routes, the system file dialogs and fetch an extension may ask for, and the bridge that lets an agent reach the
window, where extension pages run and consent is asked.
"""

from __future__ import annotations

import base64
import ipaddress
import mimetypes
import socket
import threading
import time
import uuid
import webbrowser
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from . import formext_host as kit

router = APIRouter(prefix="/api/extensions", tags=["extensions"])

PRODUCT = "formcut"
APP_NAME = "formcut"
FILES_BASE = "/api/extensions/files"
OPEN_LIMIT = 200 * 1024 * 1024
FETCH_LIMIT = 50 * 1024 * 1024
CLAIM_SECONDS = 15.0
LIST_SECONDS = 10.0
RUN_SECONDS = 150.0

_lock = threading.RLock()
_cache: dict = {"stamp": None, "extensions": []}


def app_version() -> str:
    from .main import APP_VERSION

    return APP_VERSION


def current(force: bool = False) -> list[kit.Extension]:
    stamp = kit.stamp(PRODUCT)
    with _lock:
        if force or _cache["stamp"] != stamp:
            _cache["extensions"] = kit.resolve(PRODUCT, app_version(), APP_NAME)
            _cache["stamp"] = stamp
        return list(_cache["extensions"])


@router.get("")
def list_extensions(reload: bool = False) -> dict:
    extensions = current(reload)
    return {
        "product": PRODUCT,
        "app": APP_NAME,
        "appVersion": app_version(),
        "api": kit.API,
        "root": str(kit.portal_root()),
        "stamp": list(kit.stamp(PRODUCT)),
        "extensions": [ext.public(FILES_BASE) for ext in extensions],
    }


@router.get("/stamp")
def extensions_stamp() -> dict:
    return {"stamp": list(kit.stamp(PRODUCT))}


@router.api_route("/files/{ext_id}/{version}/{rel:path}", methods=["GET", "HEAD"])
def extension_file(ext_id: str, version: str, rel: str) -> Response:
    found = kit.file_for(current(), ext_id, version, rel)
    if found is None:
        return Response(status_code=404, headers=kit.headers_for("text/plain", ""))
    path, content_type = found
    return FileResponse(path, media_type=content_type, headers=kit.headers_for(content_type, ""))


@router.post("/manage")
def manage_in_portal() -> dict:
    url = f"formai://extensions?product={PRODUCT}"
    try:
        opened = webbrowser.open(url)
    except webbrowser.Error:
        opened = False
    return {"url": url, "opened": bool(opened)}


class OpenBody(BaseModel):
    accept: list[str] = []
    multiple: bool = False
    title: str = ""


class SaveBody(BaseModel):
    name: str
    type: str = "application/octet-stream"
    data: str
    downloads: bool = False


class FetchBody(BaseModel):
    url: str
    method: str = "GET"
    headers: dict[str, str] = {}
    body: str | None = None


def _dialogs():
    from .linking import choose, dialogs_available

    if not dialogs_available():
        raise HTTPException(501, "this computer has no file dialog for the engine")
    return choose


@router.post("/open")
def open_files(body: OpenBody) -> list[dict]:
    choose = _dialogs()
    accept = [a.lower() if a.startswith(".") else f".{a.lower()}" for a in body.accept if a]
    if any(not (a[1:].isascii() and a[1:].isalnum() and len(a) <= 17) for a in accept):
        raise HTTPException(422, "accept names file extensions only")
    paths = choose("open", body.multiple, body.title or "Open", "", [a.lstrip(".") for a in accept] or None)
    if not body.multiple:
        paths = paths[:1]
    files, total = [], 0
    for raw in paths:
        path = Path(raw)
        if accept and path.suffix.lower() not in accept:
            raise HTTPException(422, f"{path.name} is not one of {', '.join(accept)}")
        if not path.is_file():
            raise HTTPException(404, f"{path.name} was not found")
        total += path.stat().st_size
        if total > OPEN_LIMIT:
            raise HTTPException(413, "the files chosen are larger than 200 MB together")
        files.append(
            {
                "name": path.name,
                "type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                "size": path.stat().st_size,
                "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
        )
    return files


@router.post("/save")
def save_file(body: SaveBody) -> dict:
    name = Path(body.name.replace("\\", "/")).name.strip().lstrip(".") or "untitled"
    try:
        data = base64.b64decode(body.data, validate=True)
    except ValueError:
        raise HTTPException(422, "data is not base64")
    if body.downloads:
        folder = Path.home() / "Downloads"
        folder.mkdir(parents=True, exist_ok=True)
        stem, suffix = Path(name).stem, Path(name).suffix
        target, n = folder / name, 2
        while target.exists():
            target, n = folder / f"{stem} ({n}){suffix}", n + 1
        target.write_bytes(data)
        return {"saved": True, "name": target.name}
    choose = _dialogs()
    paths = choose("save", False, "Save", name, None)
    if not paths:
        return {"saved": False, "name": name}
    target = Path(paths[0])
    target.write_bytes(data)
    return {"saved": True, "name": target.name}


def _public_host(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError:
        return False
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not address.is_global or address.is_multicast:
            return False
    return bool(infos)


@router.post("/fetch")
def extension_fetch(body: FetchBody) -> dict:
    parts = urlsplit(body.url)
    if parts.scheme != "https" or not parts.hostname:
        raise HTTPException(422, "only https:// addresses")
    if not _public_host(parts.hostname):
        raise HTTPException(403, f"{parts.hostname} is on this computer or its network, which extensions cannot reach")
    method = body.method.upper()
    if method not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"):
        raise HTTPException(422, f"{method} is not a method extensions may use")
    headers = {k: v for k, v in body.headers.items() if k.lower() not in ("host", "cookie", "x-formcut-local", "x-formcut-token")}
    content = base64.b64decode(body.body) if body.body else None
    try:
        with (
            httpx.Client(timeout=60, follow_redirects=False) as client,
            client.stream(method, body.url, headers=headers, content=content) as answer,
        ):
            chunks, total = [], 0
            for chunk in answer.iter_bytes():
                total += len(chunk)
                if total > FETCH_LIMIT:
                    raise HTTPException(413, "the answer is larger than 50 MB")
                chunks.append(chunk)
            return {
                "status": answer.status_code,
                "headers": {k: v for k, v in answer.headers.items() if k.lower() != "set-cookie"},
                "body": base64.b64encode(b"".join(chunks)).decode("ascii"),
            }
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"could not reach {parts.hostname}: {exc.__class__.__name__}")


class WindowAbsentError(RuntimeError):
    pass


_cond = threading.Condition()
_queue: deque[str] = deque()
_requests: dict[str, dict] = {}
_seen = {"poll": 0.0}
POLL_GAP_SECONDS = 35.0


def ask_window(action: str, payload: dict, seconds: float) -> dict:
    if time.monotonic() - _seen["poll"] > POLL_GAP_SECONDS:
        raise WindowAbsentError("the formcut window is not open: open formcut, then try again")
    rid = uuid.uuid4().hex
    entry = {"request": {"id": rid, "action": action, **payload}, "claimed": threading.Event(), "done": threading.Event(), "answer": None}
    with _cond:
        _requests[rid] = entry
        _queue.append(rid)
        _cond.notify_all()
    try:
        if not entry["claimed"].wait(CLAIM_SECONDS):
            raise WindowAbsentError("the formcut window is not open: open formcut, then try again")
        if not entry["done"].wait(seconds):
            raise WindowAbsentError(f"the formcut window did not answer within {seconds:.0f} s")
        return entry["answer"] or {}
    finally:
        with _cond:
            _requests.pop(rid, None)
            if rid in _queue:
                _queue.remove(rid)


@router.get("/agent/next")
def agent_next(wait: float = 25.0) -> dict:
    deadline = time.monotonic() + max(0.0, min(wait, 30.0))
    _seen["poll"] = time.monotonic()
    with _cond:
        while not _queue:
            left = deadline - time.monotonic()
            if left <= 0:
                _seen["poll"] = time.monotonic()
                return {"request": None}
            _cond.wait(left)
        rid = _queue.popleft()
        entry = _requests.get(rid)
    _seen["poll"] = time.monotonic()
    if entry is None:
        return {"request": None}
    entry["claimed"].set()
    return {"request": entry["request"]}


class AgentAnswer(BaseModel):
    result: object | None = None
    error: dict | None = None


@router.post("/agent/{rid}")
def agent_answer(rid: str, body: AgentAnswer) -> dict:
    with _cond:
        entry = _requests.get(rid)
    if entry is None:
        raise HTTPException(404, "that request has ended")
    entry["answer"] = {"result": body.result, "error": body.error}
    entry["done"].set()
    return {"ok": True}


def agent_list() -> dict:
    try:
        answer = ask_window("list", {}, LIST_SECONDS)
        if answer.get("error"):
            raise ValueError(str(answer["error"].get("message")))
        return {"window": True, "extensions": answer.get("result") or []}
    except WindowAbsentError:
        rows = [
            {
                "id": ext.id,
                "name": ext.name or ext.id,
                "version": ext.version,
                "source": ext.source,
                "state": ext.state,
                "reason": ext.reason,
                "commands": [{"id": c["id"], "title": c["title"]} for c in ext.commands],
            }
            for ext in current()
        ]
        return {"window": False, "note": "the formcut window is not open, so permission state is not known", "extensions": rows}


def agent_command(ext_id: str, command: str, args: object) -> dict:
    if not ext_id or not command:
        raise ValueError("id and command are required")
    try:
        answer = ask_window("run", {"extension": ext_id, "command": command, "args": args if args is not None else {}}, RUN_SECONDS)
    except WindowAbsentError as exc:
        raise ValueError(str(exc))
    if answer.get("error"):
        error = answer["error"]
        raise ValueError(f"{error.get('message')} (code {error.get('code')})")
    return {"result": answer.get("result")}
