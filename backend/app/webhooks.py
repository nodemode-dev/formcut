"""Webhooks: tell other services when an export has finished.

An automation service (Make, Zapier, n8n, or a person's own server) gets a POST
for every finished export and can hand the video on to TikTok, Instagram or
anywhere else, with the accounts and approvals that service already holds. A
webhook is an address, a secret, and whether to send the video itself or only
its details.

Every delivery is signed. X-Formcut-Timestamp carries the time and
X-Formcut-Signature an HMAC-SHA256, under the webhook's secret, of the
timestamp, a full stop and the JSON body, so a receiver can check that the
request came from this engine and is not a replay. When the video goes too, the
body is multipart: the same JSON as the field named "payload", which the
signature covers, and the video as "file", whose SHA-256 the JSON carries.
Redirects are not followed, because a signed request should reach the address
it was signed for. Failures that may pass (no answer, a server error, 408, 429)
are retried three times with growing waits; any other refusal is final. The
last outcome of each webhook is kept for the interface to show.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .paths import DATA_DIR

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])

STORE = DATA_DIR / "webhooks.json"
RETRIES = (2.0, 8.0, 30.0)  # seconds before each retry
LIMIT = 16
_lock = threading.Lock()


class WebhookInput(BaseModel):
    url: str
    sendFile: bool = False


class WebhookChange(BaseModel):
    enabled: bool | None = None
    sendFile: bool | None = None


def _read() -> list[dict]:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _write(hooks: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STORE.with_suffix(".tmp")
    temporary.write_text(json.dumps(hooks, indent=2), encoding="utf-8")
    temporary.replace(STORE)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _version() -> str:
    from .main import APP_VERSION  # main mounts this router, so it is read when a delivery is made

    return APP_VERSION


def _valid(url: str) -> str:
    address = url.strip()
    parts = urlsplit(address)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise HTTPException(422, "A webhook address starts with https:// or http:// and names a host")
    return address


def _find(hook_id: str) -> dict:
    hook = next((hook for hook in _read() if hook["id"] == hook_id), None)
    if hook is None:
        raise HTTPException(404, "no such webhook")
    return hook


def _public(hook: dict) -> dict:
    return {key: hook.get(key) for key in ("id", "url", "secret", "sendFile", "enabled", "created", "last")}


def sign(secret: str, timestamp: str, body: bytes) -> str:
    """The signature a receiver recomputes: HMAC-SHA256 of timestamp, '.', body."""
    return "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def _attempt(hook: dict, event: str, payload: dict, file: Path | None, media_type: str) -> tuple[bool, int | None, str]:
    body = json.dumps(payload, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    headers = {
        "User-Agent": f"formcut/{payload['app']['version']}",
        "X-Formcut-Event": event,
        "X-Formcut-Delivery": payload["id"],
        "X-Formcut-Timestamp": timestamp,
        "X-Formcut-Signature": sign(hook["secret"], timestamp, body),
    }
    try:
        if file is None:
            headers["Content-Type"] = "application/json"
            response = httpx.post(hook["url"], headers=headers, content=body, timeout=30.0, follow_redirects=False)
        else:
            with file.open("rb") as handle:
                form, parts = {"payload": body.decode()}, {"file": (file.name, handle, media_type)}
                response = httpx.post(hook["url"], headers=headers, data=form, files=parts, timeout=600.0, follow_redirects=False)
    except (httpx.HTTPError, OSError) as error:
        return False, None, f"could not reach it: {error.__class__.__name__}"
    if 200 <= response.status_code < 300:
        return True, response.status_code, f"HTTP {response.status_code}"
    if 300 <= response.status_code < 400:
        return False, response.status_code, f"redirected to {response.headers.get('location', '?')}; redirects are not followed"
    return False, response.status_code, f"HTTP {response.status_code}"


def _record(hook_id: str, outcome: dict) -> None:
    with _lock:
        hooks = _read()
        for hook in hooks:
            if hook["id"] == hook_id:
                hook["last"] = outcome
        _write(hooks)


def deliver(hook: dict, event: str, details: dict, file: Path | None = None, media_type: str = "video/mp4", retries=None) -> dict:
    """Send one event to one webhook, retrying what may pass, and keep the outcome."""
    payload = {"event": event, "id": uuid.uuid4().hex, "sentAt": _now(), "app": {"name": "formcut", "version": _version()}, **details}
    waits = RETRIES if retries is None else retries
    attempts, ok, code, detail = 0, False, None, ""
    for wait in (0.0, *waits):
        if wait:
            time.sleep(wait)
        attempts += 1
        ok, code, detail = _attempt(hook, event, payload, file, media_type)
        if ok or (code is not None and code < 500 and code not in (408, 429)):
            break
    outcome = {
        "at": _now(),
        "event": event,
        "status": "delivered" if ok else "failed",
        "code": code,
        "detail": detail,
        "attempts": attempts,
    }
    _record(hook["id"], outcome)
    return outcome


def announce_export(result: dict, project: dict | None = None) -> list[threading.Thread]:
    """Deliver a finished export to every enabled webhook, each in the background."""
    hooks = [hook for hook in _read() if hook.get("enabled", True)]
    if not hooks:
        return []
    path = Path(result["file"])
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    exported = {
        "name": result.get("name"),
        "mediaType": result.get("media_type"),
        "bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
        "width": result.get("width"),
        "height": result.get("height"),
        "frames": result.get("frames"),
        "codec": result.get("codec"),
        "project": (project or {}).get("name"),
    }
    media_type = result.get("media_type") or "video/mp4"
    threads = []
    for hook in hooks:
        file = path if hook.get("sendFile") else None
        thread = threading.Thread(target=deliver, args=(hook, "export.finished", {"export": exported}, file, media_type), daemon=True)
        thread.start()
        threads.append(thread)
    return threads


@router.get("")
def list_webhooks() -> list[dict]:
    return [_public(hook) for hook in _read()]


@router.post("", status_code=201)
def add_webhook(body: WebhookInput) -> dict:
    address = _valid(body.url)
    with _lock:
        hooks = _read()
        if len(hooks) >= LIMIT:
            raise HTTPException(422, f"At most {LIMIT} webhooks")
        hook = {
            "id": uuid.uuid4().hex[:12],
            "url": address,
            "secret": secrets.token_hex(24),
            "sendFile": body.sendFile,
            "enabled": True,
            "created": _now(),
            "last": None,
        }
        hooks.append(hook)
        _write(hooks)
    return _public(hook)


@router.patch("/{hook_id}")
def change_webhook(hook_id: str, body: WebhookChange) -> dict:
    with _lock:
        hooks = _read()
        hook = next((hook for hook in hooks if hook["id"] == hook_id), None)
        if hook is None:
            raise HTTPException(404, "no such webhook")
        if body.enabled is not None:
            hook["enabled"] = body.enabled
        if body.sendFile is not None:
            hook["sendFile"] = body.sendFile
        _write(hooks)
    return _public(hook)


@router.delete("/{hook_id}")
def remove_webhook(hook_id: str) -> dict:
    with _lock:
        hooks = _read()
        kept = [hook for hook in hooks if hook["id"] != hook_id]
        if len(kept) == len(hooks):
            raise HTTPException(404, "no such webhook")
        _write(kept)
    return {"removed": hook_id}


@router.post("/{hook_id}/test")
def test_webhook(hook_id: str) -> dict:
    """Send a ping now, once, so the interface can say at once whether it arrived."""
    return deliver(_find(hook_id), "ping", {"message": "A test from formcut; real deliveries carry an export."}, retries=())
