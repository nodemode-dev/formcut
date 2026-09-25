"""Stock media (Pexels) and URL import (yt-dlp) for the formcut bin.

URL import is an SSRF surface on a shared host, so a deployment that exposes
the engine beyond loopback must gate it; formcut binds loopback for one local
user, which is why no operator gate is enforced here.
Pexels guidelines require visible attribution and photographer credit;
both travel in the normalized items and into imported media records.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import providers
from .media import ingest_path

router = APIRouter(prefix="/api/stock", tags=["stock"])


# Overridable for a proxy, a mirror or a local stub; see providers.base_for.
def _pexels_base() -> str:
    return providers.base_for("pexels")


MAX_PER_PAGE = 80
_MISSING_KEY = "Pexels API key not configured. Add it in Settings, AI providers, or set PEXELS_API_KEY in .env."

_last_rate: dict[str, str | None] = {"limit": None, "remaining": None, "reset": None}


def _pexels_key() -> str:
    # Stored key first, then the environment: see providers.key_for.
    key = providers.key_for("pexels")
    if not key:
        raise HTTPException(status_code=503, detail=_MISSING_KEY)
    return key


def best_mp4(video: dict[str, Any]) -> str | None:
    files = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width")]
    if not files:
        return None
    return max(files, key=lambda f: (f.get("width") or 0) * (f.get("height") or 0)).get("link")


def normalize_photo(p: dict[str, Any]) -> dict[str, Any]:
    src = p.get("src", {})
    return {
        "id": p.get("id"),
        "type": "photo",
        "preview": src.get("medium"),
        "full": src.get("large2x") or src.get("original") or src.get("large"),
        "width": p.get("width"),
        "height": p.get("height"),
        "alt": p.get("alt"),
        "page_url": p.get("url"),
        "credit": p.get("photographer"),
        "credit_url": p.get("photographer_url"),
    }


def normalize_video(v: dict[str, Any]) -> dict[str, Any]:
    user = v.get("user") or {}
    return {
        "id": v.get("id"),
        "type": "video",
        "preview": v.get("image"),
        "full": best_mp4(v),
        "width": v.get("width"),
        "height": v.get("height"),
        "duration": v.get("duration"),
        "page_url": v.get("url"),
        "credit": user.get("name"),
        "credit_url": user.get("url"),
    }


class SearchBody(BaseModel):
    query: str = ""
    kind: str = "video"
    page: int = 1
    per_page: int = 24
    orientation: str = ""
    size: str = ""
    color: str = ""
    locale: str = ""


_ORIENTATIONS = ("landscape", "portrait", "square")
_SIZES = ("large", "medium", "small")


@router.post("/search")
def pexels_search(body: SearchBody) -> dict[str, Any]:
    key = _pexels_key()
    if body.kind not in ("video", "photo"):
        raise HTTPException(status_code=400, detail="kind must be video or photo")
    query = body.query.strip()
    if query:
        ep = "/v1/search" if body.kind == "photo" else "/v1/videos/search"
    else:
        ep = "/v1/curated" if body.kind == "photo" else "/v1/videos/popular"
    params: dict[str, Any] = {
        "per_page": min(max(body.per_page, 1), MAX_PER_PAGE),
        "page": max(body.page, 1),
    }
    if query:
        params["query"] = query
        if body.orientation in _ORIENTATIONS:
            params["orientation"] = body.orientation
        if body.size in _SIZES:
            params["size"] = body.size
        if body.color and body.kind == "photo":
            params["color"] = body.color.strip()[:12]
        if body.locale:
            params["locale"] = body.locale.strip()[:8]
    try:
        resp = httpx.get(f"{_pexels_base()}{ep}", params=params, headers={"Authorization": key}, timeout=30.0)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Pexels request failed: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"Pexels {resp.status_code}")
    for name in ("limit", "remaining", "reset"):
        value = resp.headers.get(f"X-Ratelimit-{name.capitalize()}")
        if value is not None:
            _last_rate[name] = value
    data = resp.json()
    items = (
        [normalize_photo(p) for p in data.get("photos", [])]
        if body.kind == "photo"
        else [normalize_video(v) for v in data.get("videos", [])]
    )
    return {
        "items": items,
        "page": data.get("page", params["page"]),
        "has_next": bool(data.get("next_page")),
        "attribution": "Photos provided by Pexels",
    }


@router.get("/status")
def stock_status() -> dict[str, Any]:
    return {
        "pexels": bool(providers.key_for("pexels")),
        "openverse": True,
        "rate": dict(_last_rate),
        "ytdlp": _ytdlp_cmd() is not None,
    }


# Openverse: openly licensed audio (Freesound, Jamendo, Wikimedia and more)
# and images, searched without a key; every record carries its licence and
# creator, which travel into the media record as Pexels' credit does. The
# import takes the record's id and reads the file URL back from Openverse
# itself, so the engine never fetches a URL a caller typed.
OPENVERSE = "https://api.openverse.org/v1"
_OPENVERSE_KINDS = {"audio": "audio", "image": "images"}


def _licence_label(item: dict[str, Any]) -> str:
    licence = str(item.get("license") or "").upper()
    if licence == "PDM":
        return "Public domain"
    if licence == "CC0":
        return "CC0"
    version = str(item.get("license_version") or "")
    return f"CC {licence} {version}".strip() if licence else ""


def normalize_openverse(item: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "type": kind,
        "preview": item.get("thumbnail") if kind == "image" else None,
        "full": item.get("url"),
        "title": item.get("title") or "",
        "width": item.get("width"),
        "height": item.get("height"),
        "duration": (float(item["duration"]) / 1000) if kind == "audio" and item.get("duration") else None,
        "page_url": item.get("foreign_landing_url"),
        "credit": item.get("creator"),
        "credit_url": item.get("creator_url"),
        "license": _licence_label(item),
        "license_url": item.get("license_url"),
        "source": item.get("source"),
    }


class OpenverseSearchBody(BaseModel):
    query: str = ""
    kind: str = "audio"
    page: int = 1
    per_page: int = 20


# Openverse allows anonymous callers 20 results a page; a key would raise it.
_OPENVERSE_PAGE = 20


@router.post("/openverse/search")
def openverse_search(body: OpenverseSearchBody) -> dict[str, Any]:
    kind = body.kind if body.kind in _OPENVERSE_KINDS else "audio"
    if not body.query.strip():
        return {"items": [], "page": 1, "total": 0, "kind": kind}
    params = {"q": body.query.strip()[:200], "page": max(1, body.page), "page_size": max(1, min(_OPENVERSE_PAGE, body.per_page))}
    try:
        resp = httpx.get(f"{OPENVERSE}/{_OPENVERSE_KINDS[kind]}/", params=params, timeout=30.0, headers={"User-Agent": "formcut"})
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Openverse could not be reached: {e.__class__.__name__}") from e
    if resp.status_code == 429:
        raise HTTPException(status_code=429, detail="Openverse is rate-limiting anonymous searches; try again in a minute")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Openverse answered {resp.status_code}")
    data = resp.json()
    return {
        "items": [normalize_openverse(item, kind) for item in data.get("results") or [] if item.get("url")],
        "page": body.page,
        "total": int(data.get("result_count") or 0),
        "kind": kind,
        "attribution": "Openverse; each item carries its own licence and creator",
    }


class OpenverseImportBody(BaseModel):
    id: str
    kind: str = "audio"


@router.post("/openverse/import", status_code=201)
def openverse_import(body: OpenverseImportBody) -> dict[str, Any]:
    kind = body.kind if body.kind in _OPENVERSE_KINDS else "audio"
    if not body.id.replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="id must be an Openverse record id")
    try:
        detail = httpx.get(f"{OPENVERSE}/{_OPENVERSE_KINDS[kind]}/{body.id}/", timeout=30.0, headers={"User-Agent": "formcut"})
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Openverse could not be reached: {e.__class__.__name__}") from e
    if detail.status_code != 200:
        raise HTTPException(status_code=404, detail="Openverse has no record by that id")
    item = normalize_openverse(detail.json(), kind)
    url = str(item.get("full") or "")
    if not url.startswith("https://"):
        raise HTTPException(status_code=502, detail="the record has no https file URL")
    try:
        resp = httpx.get(url, timeout=180.0, follow_redirects=True, headers={"User-Agent": "formcut"})
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"fetch failed: {e.__class__.__name__}") from e
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="failed to fetch media")
    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
    ext = {
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/ogg": ".ogg",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
        "audio/flac": ".flac",
        "audio/mp4": ".m4a",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(content_type) or (".mp3" if kind == "audio" else ".jpg")
    tmp = Path(tempfile.gettempdir()) / f"formcut_openverse_{uuid.uuid4().hex}{ext}"
    tmp.write_bytes(resp.content)
    safe = "".join(ch for ch in str(item.get("title") or "openverse") if ch.isalnum() or ch in " -_")[:60].strip() or "openverse"
    try:
        return ingest_path(
            tmp,
            f"{safe}{ext}",
            extra={
                "source": "openverse",
                "credit": item.get("credit"),
                "credit_url": item.get("credit_url"),
                "page_url": item.get("page_url"),
                "license": item.get("license"),
                "license_url": item.get("license_url"),
                "attribution": f"{item.get('title') or 'Untitled'} by {item.get('credit') or 'unknown'}, {item.get('license') or 'licence unknown'}, via Openverse",
            },
        )
    finally:
        tmp.unlink(missing_ok=True)


_PEXELS_HOSTS = (
    "https://images.pexels.com/",
    "https://videos.pexels.com/",
    "https://static-videos.pexels.com/",
    "https://player.vimeo.com/external/",
)


class PexelsImportBody(BaseModel):
    url: str
    kind: str = "video"
    name: str = "pexels"
    credit: str | None = None
    page_url: str | None = None


@router.post("/import", status_code=201)
def pexels_import(body: PexelsImportBody) -> dict[str, Any]:
    if not body.url.startswith(_PEXELS_HOSTS):
        raise HTTPException(status_code=400, detail="url must be a Pexels media url")
    ext = ".mp4" if body.kind == "video" else ".jpg"
    try:
        resp = httpx.get(body.url, timeout=180.0, follow_redirects=True)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"fetch failed: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="failed to fetch media")
    tmp = Path(tempfile.gettempdir()) / f"formcut_stock_{uuid.uuid4().hex}{ext}"
    tmp.write_bytes(resp.content)
    safe = "".join(ch for ch in body.name if ch.isalnum() or ch in " -_")[:60] or "pexels"
    return ingest_path(
        tmp,
        f"{safe}{ext}",
        extra={
            "source": "pexels",
            "credit": body.credit,
            "page_url": body.page_url,
            "attribution": "Photos provided by Pexels",
        },
    )


def _ytdlp_cmd() -> list[str] | None:
    # In a frozen (PyInstaller) engine sys.executable is the app binary, so
    # the -m route is meaningless there; portable builds rely on yt-dlp on
    # PATH, the same tier-1 tool policy as ffmpeg.
    if not getattr(sys, "frozen", False):
        try:
            import yt_dlp  # noqa: F401

            return [sys.executable, "-m", "yt_dlp"]
        except ImportError:
            pass
    found = shutil.which("yt-dlp")
    return [found] if found else None


_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


class UrlImportBody(BaseModel):
    url: str


def _run_url_import(job_id: str, url: str) -> None:
    cmd = _ytdlp_cmd()
    if cmd is None:
        with _jobs_lock:
            _jobs[job_id].update(status="error", error="yt-dlp is not installed")
        return
    workdir = Path(tempfile.mkdtemp(prefix="formcut_ytdlp_"))
    args = [
        *cmd,
        "--no-playlist",
        "--restrict-filenames",
        "-f",
        "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "--merge-output-format",
        "mp4",
        "-o",
        str(workdir / "%(title).60s.%(ext)s"),
        url,
    ]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, check=False, timeout=600)
        if proc.returncode != 0:
            with _jobs_lock:
                _jobs[job_id].update(status="error", error=(proc.stderr or "yt-dlp failed")[-300:])
            return
        files = sorted(workdir.iterdir(), key=lambda p: p.stat().st_size, reverse=True)
        if not files:
            with _jobs_lock:
                _jobs[job_id].update(status="error", error="download produced no file")
            return
        item = ingest_path(files[0], files[0].name, extra={"source": "url", "page_url": url})
        with _jobs_lock:
            _jobs[job_id].update(status="done", media=item)
    except (OSError, subprocess.SubprocessError) as exc:
        with _jobs_lock:
            _jobs[job_id].update(status="error", error=str(exc)[-300:])
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


@router.post("/url", status_code=202)
def url_import(body: UrlImportBody) -> dict[str, str]:
    url = body.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="a full http or https url is required")
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        finished = [k for k, v in _jobs.items() if v.get("status") in ("done", "error")]
        for old in finished[:-24] if len(finished) > 24 else []:
            _jobs.pop(old, None)
        _jobs[job_id] = {"status": "running"}
    threading.Thread(target=_run_url_import, args=(job_id, url), daemon=True).start()
    return {"job_id": job_id}


@router.get("/url/{job_id}")
def url_import_status(job_id: str) -> dict[str, Any]:
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return {"job_id": job_id, **job}
