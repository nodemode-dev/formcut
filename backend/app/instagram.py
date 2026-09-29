"""Instagram: publish an export or a bin video as a Reel.

Publishing follows Meta's resumable upload for apps using Facebook Login for
Business: create a REELS container with upload_type=resumable on
graph.facebook.com, which returns the container and an upload address on
rupload.facebook.com; send the file there in one POST with the headers
Authorization: OAuth <token>, offset: 0 and file_size; poll the container's
status_code until FINISHED; then publish it with media_publish.

The access token comes from the owner's Meta app and is stored here, in a file
only the engine's owner can read; it never reaches the browser. The Instagram
professional account is found behind it: through the Pages of a user token, or
directly on a Page token. Reels must be H.264 or HEVC, so the video's codec is
checked before anything is sent, rather than failing inside Meta after a whole
upload.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import jobs, media
from .durable import read_json, write_json
from .paths import DATA_DIR

router = APIRouter(tags=["instagram"])

STORE = DATA_DIR / "instagram.json"
CODECS = ("h264", "hevc")
POLL = 5.0
WAIT_FOR = 1800.0  # seconds Meta may take to process a Reel before this gives up
ACCOUNT_FIELDS = "instagram_business_account{id,username}"


class ConnectInput(BaseModel):
    token: str


class PostInput(BaseModel):
    jobId: str | None = None
    mediaId: str | None = None
    caption: str = ""
    shareToFeed: bool = True


class InstagramError(RuntimeError):
    """Meta refused or failed; the message says which."""


def _graph() -> str:
    version = os.environ.get("INSTAGRAM_GRAPH_VERSION", "") or "v25.0"
    return f"{os.environ.get('INSTAGRAM_GRAPH_BASE', '').rstrip('/') or 'https://graph.facebook.com'}/{version}"


def _read() -> dict:
    return read_json(STORE, {})  # durable.py: a damaged file set aside and its backup read


def _write(data: dict) -> None:
    write_json(STORE, data, private=True)


def _reply(response: httpx.Response) -> dict:
    reply = response.json() if response.content else {}
    problem = reply.get("error") if isinstance(reply, dict) else None
    if response.status_code >= 400 or problem:
        message = (problem or {}).get("message") or f"HTTP {response.status_code}"
        raise InstagramError(f"Meta refused: {message}")
    return reply


def _get(path: str, token: str, **params) -> dict:
    try:
        return _reply(httpx.get(f"{_graph()}{path}", params={**params, "access_token": token}, timeout=60.0))
    except httpx.HTTPError as error:
        raise InstagramError(f"Could not reach Meta: {error.__class__.__name__}") from error


def _post(path: str, token: str, **params) -> dict:
    try:
        return _reply(httpx.post(f"{_graph()}{path}", data={**params, "access_token": token}, timeout=60.0))
    except httpx.HTTPError as error:
        raise InstagramError(f"Could not reach Meta: {error.__class__.__name__}") from error


def find_account(token: str) -> dict:
    """The Instagram professional account behind a user token's Pages, or on a Page token."""
    for page in _get("/me/accounts", token, fields=ACCOUNT_FIELDS).get("data", []):
        if page.get("instagram_business_account"):
            return page["instagram_business_account"]
    own = _get("/me", token, fields=ACCOUNT_FIELDS).get("instagram_business_account")
    if own:
        return own
    raise InstagramError("No Instagram professional account is linked to a Facebook Page for this token")


def codec(path: Path) -> str:
    program = shutil.which("ffprobe") or "ffprobe"
    command = [program, "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)]
    return subprocess.run(command, capture_output=True, text=True, check=False).stdout.strip()


def _source(body: PostInput) -> Path:
    if body.jobId:
        state = jobs.status(body.jobId)
        found = (state.get("result") or {}).get("file")
        if state.get("status") != "done" or not found:
            raise HTTPException(422, "that export has not finished")
        return Path(found)
    if body.mediaId:
        item = media._find(body.mediaId)
        if item.get("kind") != "video":
            raise HTTPException(422, "only video can go to Instagram as a Reel")
        path = next(media.MEDIA_DIR.glob(f"{body.mediaId}.*"), None)
        if path is None:
            raise HTTPException(404, "file missing")
        return path
    raise HTTPException(422, "name an export (jobId) or a bin item (mediaId)")


def _publish(body: PostInput, path: Path, account: dict):
    def operation(job_id: str, report, cancelled) -> dict:
        token, user = account["token"], account["userId"]
        options = {
            "media_type": "REELS",
            "upload_type": "resumable",
            "caption": body.caption,
            "share_to_feed": str(body.shareToFeed).lower(),
        }
        created = _post(f"/{user}/media", token, **options)
        size = path.stat().st_size
        headers = {"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)}
        report(0.1)
        try:
            with path.open("rb") as handle:
                sent = httpx.post(created["uri"], headers=headers, content=handle.read(), timeout=1800.0)
        except httpx.HTTPError as error:
            raise InstagramError(f"The upload did not finish: {error.__class__.__name__}") from error
        _reply(sent)
        report(0.6)
        deadline = time.time() + WAIT_FOR
        while True:
            if cancelled():
                raise InterruptedError
            status = _get(f"/{created['id']}", token, fields="status_code,status").get("status_code")
            if status == "FINISHED":
                break
            if status in ("ERROR", "EXPIRED"):
                raise InstagramError(f"Instagram could not take the video: {status}")
            if time.time() > deadline:
                raise InstagramError("Instagram took too long to process the video")
            report(0.75)
            time.sleep(POLL)
        published = _post(f"/{user}/media_publish", token, creation_id=created["id"])
        return {"mediaId": published.get("id"), "containerId": created["id"]}

    return operation


# Routes --------------------------------------------------------------------------


@router.get("/api/connect/instagram")
def state() -> dict:
    account = _read().get("account")
    return {"connected": bool(account), "userId": account and account["userId"], "username": account and account.get("username")}


@router.put("/api/connect/instagram")
def connect(body: ConnectInput) -> dict:
    token = body.token.strip()
    if not token:
        raise HTTPException(422, "paste an access token from the Meta app")
    try:
        found = find_account(token)
    except InstagramError as failure:
        raise HTTPException(422, str(failure)) from failure
    _write({"account": {"token": token, "userId": found["id"], "username": found.get("username", "")}})
    return state()


@router.delete("/api/connect/instagram")
def disconnect() -> dict:
    _write({})
    return state()


@router.post("/api/publish/instagram")
def publish(body: PostInput) -> dict:
    account = _read().get("account")
    if not account:
        raise HTTPException(409, "Connect an Instagram account first")
    path = _source(body)
    found = codec(path)
    if found not in CODECS:
        reason = f"Instagram Reels need H.264 or HEVC video; this one is {found or 'unreadable'}."
        raise HTTPException(422, f"{reason} Export with an H.264 encoder first.")
    return jobs.submit("instagram", _publish(body, path, account))
