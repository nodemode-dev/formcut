"""TikTok: sign in, then post an export or a bin item, directly or as a draft.

Sign-in follows TikTok's rules for desktop apps: PKCE with a code challenge that
is the hex SHA-256 of the verifier (TikTok's form, not base64url), a redirect to
this engine on 127.0.0.1 whose registered form uses a wildcard port, and a state
token checked on the way back. TikTok wants the client secret and refresh token
kept on a server, so the code is exchanged in one of two ways: through a token
relay the app's owner hosts, which holds the secret, or directly with a secret
stored here, for a person using their own TikTok developer app. Tokens stay in
the engine, in a file only its owner can read, and never reach the browser.

Posting uses the Content Posting API. A direct post (video.publish) first reads
the creator's allowed privacy levels and sends one of them; TikTok keeps posts
from an unaudited app private whatever is asked. A draft (video.upload) lands
in the person's TikTok inbox to finish there. The video goes up as
FILE_UPLOAD in chunks: one chunk up to 64 MB, else 10 MB chunks whose count is
the size divided by the chunk size rounded down, the last absorbing the rest.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from . import jobs, media
from .paths import DATA_DIR

router = APIRouter(tags=["tiktok"])

STORE = DATA_DIR / "tiktok.json"
SCOPES = "user.info.basic,video.upload,video.publish"
SINGLE = 64_000_000  # up to this, the whole file is one chunk
CHUNK = 10_000_000
POLL = 5.0
PENDING_FOR = 600.0  # seconds a sign-in may take
_pending: dict[str, dict] = {}
_lock = threading.Lock()


class AppInput(BaseModel):
    clientKey: str
    clientSecret: str | None = None
    relay: str | None = None


class PostInput(BaseModel):
    jobId: str | None = None
    mediaId: str | None = None
    mode: str = "draft"  # draft | direct
    title: str = ""
    privacyLevel: str | None = None
    disableComment: bool = False
    disableDuet: bool = False
    disableStitch: bool = False


class TikTokError(RuntimeError):
    """TikTok refused or failed; the message says which."""


def _api() -> str:
    return os.environ.get("TIKTOK_API_BASE", "").rstrip("/") or "https://open.tiktokapis.com"


def _authorize() -> str:
    return os.environ.get("TIKTOK_AUTH_URL", "") or "https://www.tiktok.com/v2/auth/authorize/"


def _read() -> dict:
    try:
        return json.loads(STORE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write(data: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STORE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(STORE)


def _app() -> dict:
    stored = _read().get("app", {})
    return {
        "clientKey": stored.get("clientKey") or os.environ.get("TIKTOK_CLIENT_KEY", ""),
        "clientSecret": stored.get("clientSecret") or os.environ.get("TIKTOK_CLIENT_SECRET", ""),
        "relay": (stored.get("relay") or os.environ.get("TIKTOK_RELAY", "")).rstrip("/"),
    }


def challenge(verifier: str) -> str:
    """TikTok's PKCE challenge: the hex SHA-256 of the verifier."""
    return hashlib.sha256(verifier.encode()).hexdigest()


def chunks(size: int) -> tuple[int, int]:
    """(chunk_size, total_chunk_count) under TikTok's media transfer rules."""
    if size <= SINGLE:
        return size, 1
    return CHUNK, size // CHUNK


def _exchange(form: dict) -> dict:
    """Trade a code or a refresh token for tokens, through the relay or with the local secret."""
    app = _app()
    try:
        if app["relay"]:
            response = httpx.post(f"{app['relay']}/tiktok/token", json=form, timeout=30.0)
        elif app["clientSecret"]:
            credentials = {"client_key": app["clientKey"], "client_secret": app["clientSecret"]}
            response = httpx.post(f"{_api()}/v2/oauth/token/", data={**form, **credentials}, timeout=30.0)
        else:
            raise TikTokError("Set a token relay or a client secret for TikTok first")
    except httpx.HTTPError as error:
        raise TikTokError(f"Could not reach the token service: {error.__class__.__name__}") from error
    reply = response.json() if response.content else {}
    if response.status_code >= 400 or "access_token" not in reply:
        raise TikTokError(f"TikTok refused the sign-in: {reply.get('error_description') or reply.get('error') or response.status_code}")
    now = time.time()
    return {
        "accessToken": reply["access_token"],
        "refreshToken": reply.get("refresh_token", ""),
        "openId": reply.get("open_id", ""),
        "scope": reply.get("scope", ""),
        "expiresAt": now + float(reply.get("expires_in", 0)),
        "refreshExpiresAt": now + float(reply.get("refresh_expires_in", 0)),
    }


def _token() -> str:
    """A live access token, refreshed when it is within a minute of expiring."""
    data = _read()
    account = data.get("account")
    if not account:
        raise TikTokError("Connect a TikTok account first")
    if account["expiresAt"] - time.time() < 60:
        fresh = _exchange({"grant_type": "refresh_token", "refresh_token": account["refreshToken"]})
        data["account"] = {**account, **fresh}
        _write(data)
        account = data["account"]
    return account["accessToken"]


def _call(path: str, body: dict) -> dict:
    headers = {"Authorization": f"Bearer {_token()}", "Content-Type": "application/json; charset=UTF-8"}
    try:
        response = httpx.post(f"{_api()}{path}", headers=headers, json=body, timeout=60.0)
    except httpx.HTTPError as error:
        raise TikTokError(f"Could not reach TikTok: {error.__class__.__name__}") from error
    reply = response.json() if response.content else {}
    problem = reply.get("error") or {}
    if response.status_code >= 400 or problem.get("code", "ok") != "ok":
        raise TikTokError(f"TikTok answered {problem.get('code') or response.status_code}: {problem.get('message') or 'no reason given'}")
    return reply.get("data") or {}


def creator() -> dict:
    return _call("/v2/post/publish/creator_info/query/", {})


def _upload(url: str, path: Path, size: int, chunk_size: int, count: int, media_type: str, report, cancelled) -> None:
    with path.open("rb") as handle, httpx.Client(timeout=600.0) as client:
        for index in range(count):
            if cancelled():
                raise InterruptedError
            first = index * chunk_size
            last = size - 1 if index == count - 1 else first + chunk_size - 1
            handle.seek(first)
            piece = handle.read(last - first + 1)
            headers = {"Content-Range": f"bytes {first}-{last}/{size}", "Content-Type": media_type}
            try:
                response = client.put(url, headers=headers, content=piece)
            except httpx.HTTPError as error:
                raise TikTokError(f"Upload of chunk {index + 1} failed: {error.__class__.__name__}") from error
            if response.status_code not in (200, 201, 206):
                raise TikTokError(f"Upload of chunk {index + 1} failed: HTTP {response.status_code}")
            report(0.1 + 0.6 * (index + 1) / count)


def _source(body: PostInput) -> tuple[Path, str]:
    if body.jobId:
        state = jobs.status(body.jobId)
        found = (state.get("result") or {}).get("file")
        if state.get("status") != "done" or not found:
            raise HTTPException(422, "that export has not finished")
        return Path(found), (state.get("result") or {}).get("media_type") or "video/mp4"
    if body.mediaId:
        item = media._find(body.mediaId)
        if item.get("kind") != "video":
            raise HTTPException(422, "only video can go to TikTok")
        path = next(media.MEDIA_DIR.glob(f"{body.mediaId}.*"), None)
        if path is None:
            raise HTTPException(404, "file missing")
        return path, "video/quicktime" if path.suffix.lower() == ".mov" else f"video/{path.suffix.lstrip('.').lower() or 'mp4'}"
    raise HTTPException(422, "name an export (jobId) or a bin item (mediaId)")


def _post(body: PostInput, path: Path, media_type: str):
    def operation(job_id: str, report, cancelled) -> dict:
        size = path.stat().st_size
        chunk_size, count = chunks(size)
        source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk_size, "total_chunk_count": count}
        if body.mode == "direct":
            info = {"title": body.title, "privacy_level": body.privacyLevel, "disable_comment": body.disableComment}
            info.update(disable_duet=body.disableDuet, disable_stitch=body.disableStitch)
            started = _call("/v2/post/publish/video/init/", {"post_info": info, "source_info": source})
        else:
            started = _call("/v2/post/publish/inbox/video/init/", {"source_info": source})
        report(0.1)
        _upload(started["upload_url"], path, size, chunk_size, count, media_type, report, cancelled)
        while True:
            if cancelled():
                raise InterruptedError
            state = _call("/v2/post/publish/status/fetch/", {"publish_id": started["publish_id"]})
            if state.get("status") in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
                return {"publishId": started["publish_id"], "status": state["status"], "mode": body.mode}
            if state.get("status") == "FAILED":
                raise TikTokError(f"TikTok could not take the video: {state.get('fail_reason') or 'no reason given'}")
            report(0.75)
            time.sleep(POLL)

    return operation


# Routes --------------------------------------------------------------------------


@router.put("/api/connect/tiktok/app")
def set_app(body: AppInput) -> dict:
    data = _read()
    data["app"] = {
        "clientKey": body.clientKey.strip(),
        "clientSecret": (body.clientSecret or "").strip(),
        "relay": (body.relay or "").strip(),
    }
    _write(data)
    return state()


@router.get("/api/connect/tiktok")
def state() -> dict:
    app, account = _app(), _read().get("account")
    mode = "relay" if app["relay"] else "local" if app["clientSecret"] else None
    public = {"openId": account["openId"], "scope": account["scope"], "expiresAt": account["expiresAt"]} if account else None
    return {"configured": bool(app["clientKey"] and mode), "mode": mode, "connected": bool(account), "account": public}


@router.post("/api/connect/tiktok/start")
def start(request: Request) -> dict:
    """The TikTok sign-in address; the interface opens it in the system browser."""
    app = _app()
    if not app["clientKey"]:
        raise HTTPException(409, "Set the TikTok client key first")
    verifier, token = secrets.token_urlsafe(48), secrets.token_urlsafe(24)
    redirect = f"http://127.0.0.1:{request.url.port}/api/connect/tiktok/callback/"
    now = time.time()
    with _lock:
        for key in [key for key, value in _pending.items() if now - value["at"] > PENDING_FOR]:
            del _pending[key]
        _pending[token] = {"verifier": verifier, "redirect": redirect, "at": now}
    query = {"client_key": app["clientKey"], "response_type": "code", "scope": SCOPES, "redirect_uri": redirect, "state": token}
    query.update(code_challenge=challenge(verifier), code_challenge_method="S256")
    return {"url": f"{_authorize()}?{urlencode(query)}"}


@router.get("/api/connect/tiktok/callback/", response_class=HTMLResponse)
def callback(state: str = "", code: str = "", error: str = "", error_description: str = "") -> HTMLResponse:
    with _lock:
        pending = _pending.pop(state, None)
    if pending is None or time.time() - pending["at"] > PENDING_FOR:
        return HTMLResponse("<p>This TikTok sign-in is unknown or expired. Start again from formcut.</p>", status_code=400)
    if error or not code:
        return HTMLResponse(f"<p>TikTok sign-in did not finish: {error_description or error or 'no code'}.</p>", status_code=400)
    form = {"code": code, "grant_type": "authorization_code", "redirect_uri": pending["redirect"], "code_verifier": pending["verifier"]}
    try:
        account = _exchange(form)
    except TikTokError as failure:
        return HTMLResponse(f"<p>{failure}</p>", status_code=502)
    data = _read()
    data["account"] = account
    _write(data)
    return HTMLResponse("<p>Connected to TikTok. You can close this tab and return to formcut.</p>")


@router.delete("/api/connect/tiktok")
def disconnect() -> dict:
    data = _read()
    data.pop("account", None)
    _write(data)
    return state()


@router.get("/api/publish/tiktok/creator")
def creator_info() -> dict:
    try:
        return creator()
    except TikTokError as failure:
        raise HTTPException(502, str(failure))


@router.post("/api/publish/tiktok")
def publish(body: PostInput) -> dict:
    if body.mode not in ("draft", "direct"):
        raise HTTPException(422, "mode is draft or direct")
    path, media_type = _source(body)
    if body.mode == "direct":
        try:
            allowed = creator().get("privacy_level_options") or []
        except TikTokError as failure:
            raise HTTPException(502, str(failure))
        if body.privacyLevel not in allowed:
            raise HTTPException(422, f"choose one of this account's privacy levels: {', '.join(allowed) or 'none offered'}")
    return jobs.submit("tiktok", _post(body, path, media_type))
