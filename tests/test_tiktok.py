"""TikTok: desktop sign-in and the Content Posting API, against a fake that follows TikTok's documentation."""

import hashlib
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
from app import jobs, tiktok
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
OK = {"code": "ok", "message": ""}


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _reply(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def do_POST(self):
        state, raw = self.server.state, self._body()
        if self.path in ("/v2/oauth/token/", "/relay/tiktok/token"):
            form = {key: values[0] for key, values in parse_qs(raw.decode()).items()} if self.path.startswith("/v2") else json.loads(raw)
            state["token_forms"].append((self.path, form))
            fresh = form["grant_type"] == "refresh_token"
            tokens = {
                "access_token": "act.2" if fresh else "act.1",
                "refresh_token": "rft.1",
                "open_id": "open-1",
                "scope": "video.upload,video.publish",
            }
            self._reply(200, {**tokens, "expires_in": 86400, "refresh_expires_in": 31536000, "token_type": "Bearer"})
            return
        state["calls"].append((self.path, self.headers.get("Authorization"), json.loads(raw or b"{}")))
        if self.path == "/v2/post/publish/creator_info/query/":
            info = {"creator_username": "maker", "privacy_level_options": ["MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"]}
            self._reply(200, {"data": info, "error": OK})
        elif self.path.endswith("/video/init/"):
            publish_id = "v_inbox_1" if "inbox" in self.path else "v_pub_1"
            self._reply(200, {"data": {"publish_id": publish_id, "upload_url": f"{state['base']}/upload/1"}, "error": OK})
        else:
            state["polls"] += 1
            done = "SEND_TO_USER_INBOX" if state["calls"][-1][2]["publish_id"] == "v_inbox_1" else "PUBLISH_COMPLETE"
            if state["outcome"] == "failed":
                self._reply(200, {"data": {"status": "FAILED", "fail_reason": "file_format_check_failed"}, "error": OK})
            else:
                self._reply(200, {"data": {"status": "PROCESSING_UPLOAD" if state["polls"] < 2 else done}, "error": OK})

    def do_PUT(self):
        state = self.server.state
        state["puts"].append((self.headers.get("Content-Range"), self.headers.get("Authorization"), self._body()))
        last = self.headers["Content-Range"].split("/")[0].split("-")[1]
        total = self.headers["Content-Range"].split("/")[1]
        self.send_response(201 if int(last) + 1 == int(total) else 206)
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture
def fake(tmp_path, monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    server.state = {"base": base, "token_forms": [], "calls": [], "puts": [], "polls": 0, "outcome": "ok"}
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(tiktok, "STORE", tmp_path / "tiktok.json")
    monkeypatch.setattr(tiktok, "POLL", 0.01)
    monkeypatch.setenv("TIKTOK_API_BASE", base)
    monkeypatch.setenv("TIKTOK_AUTH_URL", f"{base}/v2/auth/authorize/")
    yield server.state
    server.shutdown()


def _connect(expires_in=3600.0):
    tiktok._write({"app": {"clientKey": "key-1", "clientSecret": "local-secret", "relay": ""}, "account": {
        "accessToken": "act.1", "refreshToken": "rft.1", "openId": "open-1", "scope": "video.upload,video.publish",
        "expiresAt": time.time() + expires_in, "refreshExpiresAt": time.time() + 86400,
    }})  # fmt: skip


def _export(tmp_path, content):
    video = tmp_path / "cut.mp4"
    video.write_bytes(content)
    job = jobs.submit("export", lambda job_id, report, cancelled: {"file": str(video), "media_type": "video/mp4"})
    deadline = time.time() + 10
    while jobs.status(job["job_id"])["status"] != "done" and time.time() < deadline:
        time.sleep(0.02)
    return job["job_id"]


def _finish(job, seconds=20.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        state = jobs.status(job["job_id"])
        if state["status"] in ("done", "error", "cancelled"):
            return state
        time.sleep(0.05)
    raise AssertionError("the job did not finish")


def test_the_challenge_is_the_hex_sha256_of_the_verifier():
    assert tiktok.challenge("abc") == hashlib.sha256(b"abc").hexdigest()


def test_chunks_follow_tiktoks_media_transfer_rules():
    assert tiktok.chunks(4_194_304) == (4_194_304, 1)
    assert tiktok.chunks(64_000_000) == (64_000_000, 1)
    size = 150_000_123
    chunk_size, count = tiktok.chunks(size)
    assert (chunk_size, count) == (10_000_000, 15)
    last = size - (count - 1) * chunk_size
    assert 5_000_000 <= chunk_size <= 64_000_000 and chunk_size <= last <= 128_000_000


def test_sign_in_uses_pkce_on_the_loopback_and_keeps_tokens_private(fake):
    client.put("/api/connect/tiktok/app", json={"clientKey": "key-1", "clientSecret": "local-secret"})
    query = parse_qs(urlsplit(client.post("/api/connect/tiktok/start").json()["url"]).query)
    assert query["redirect_uri"] == ["http://127.0.0.1:8123/api/connect/tiktok/callback/"]
    assert (query["client_key"], query["response_type"], query["code_challenge_method"]) == (["key-1"], ["code"], ["S256"])
    page = client.get("/api/connect/tiktok/callback/", params={"state": query["state"][0], "code": "the-code"})
    assert page.status_code == 200 and "Connected to TikTok" in page.text
    path, form = fake["token_forms"][0]
    assert path == "/v2/oauth/token/" and (form["code"], form["client_secret"], form["client_key"]) == ("the-code", "local-secret", "key-1")
    assert hashlib.sha256(form["code_verifier"].encode()).hexdigest() == query["code_challenge"][0]
    shown = client.get("/api/connect/tiktok").json()
    assert (shown["connected"], shown["mode"], shown["account"]["openId"]) == (True, "local", "open-1")
    assert "act.1" not in json.dumps(shown) and "rft.1" not in json.dumps(shown)
    assert os.stat(tiktok.STORE).st_mode & 0o777 == 0o600


def test_an_unknown_or_replayed_sign_in_is_refused(fake):
    client.put("/api/connect/tiktok/app", json={"clientKey": "key-1", "clientSecret": "local-secret"})
    assert client.get("/api/connect/tiktok/callback/", params={"state": "forged", "code": "x"}).status_code == 400
    token = parse_qs(urlsplit(client.post("/api/connect/tiktok/start").json()["url"]).query)["state"][0]
    assert client.get("/api/connect/tiktok/callback/", params={"state": token, "code": "the-code"}).status_code == 200
    assert client.get("/api/connect/tiktok/callback/", params={"state": token, "code": "the-code"}).status_code == 400


def test_a_relay_exchanges_the_code_and_no_secret_is_sent(fake):
    client.put("/api/connect/tiktok/app", json={"clientKey": "key-1", "relay": f"{fake['base']}/relay"})
    token = parse_qs(urlsplit(client.post("/api/connect/tiktok/start").json()["url"]).query)["state"][0]
    client.get("/api/connect/tiktok/callback/", params={"state": token, "code": "the-code"})
    path, form = fake["token_forms"][0]
    assert path == "/relay/tiktok/token" and "client_secret" not in form and form["code_verifier"]
    assert client.get("/api/connect/tiktok").json()["mode"] == "relay"


def test_a_direct_post_uses_an_offered_privacy_level_and_uploads_in_chunks(tmp_path, fake, monkeypatch):
    _connect()
    monkeypatch.setattr(tiktok, "SINGLE", 100)
    monkeypatch.setattr(tiktok, "CHUNK", 40)
    content = bytes(range(130))
    job_id = _export(tmp_path, content)
    refused = client.post("/api/publish/tiktok", json={"jobId": job_id, "mode": "direct", "privacyLevel": "PUBLIC_TO_EVERYONE"})
    assert refused.status_code == 422 and "SELF_ONLY" in refused.json()["detail"]
    post = {"jobId": job_id, "mode": "direct", "title": "Hi", "privacyLevel": "SELF_ONLY"}
    state = _finish(client.post("/api/publish/tiktok", json=post).json())
    assert state["status"] == "done" and state["result"] == {"publishId": "v_pub_1", "status": "PUBLISH_COMPLETE", "mode": "direct"}
    init = next(call for call in fake["calls"] if call[0] == "/v2/post/publish/video/init/")
    assert init[1] == "Bearer act.1" and init[2]["post_info"]["privacy_level"] == "SELF_ONLY" and init[2]["post_info"]["title"] == "Hi"
    assert init[2]["source_info"] == {"source": "FILE_UPLOAD", "video_size": 130, "chunk_size": 40, "total_chunk_count": 3}
    assert [put[0] for put in fake["puts"]] == ["bytes 0-39/130", "bytes 40-79/130", "bytes 80-129/130"]
    assert b"".join(put[2] for put in fake["puts"]) == content and {put[1] for put in fake["puts"]} == {None}


def test_a_draft_goes_to_the_inbox_without_post_details(tmp_path, fake):
    _connect()
    state = _finish(client.post("/api/publish/tiktok", json={"jobId": _export(tmp_path, b"v" * 50), "mode": "draft"}).json())
    assert state["result"] == {"publishId": "v_inbox_1", "status": "SEND_TO_USER_INBOX", "mode": "draft"}
    init = next(call for call in fake["calls"] if "init" in call[0])
    assert init[0] == "/v2/post/publish/inbox/video/init/" and "post_info" not in init[2]


def test_an_expiring_token_is_refreshed_first(fake):
    _connect(expires_in=10)
    assert tiktok.creator()["creator_username"] == "maker"
    assert fake["token_forms"][0][1]["grant_type"] == "refresh_token" and fake["calls"][0][1] == "Bearer act.2"


def test_a_failed_post_reports_tiktoks_reason(tmp_path, fake):
    _connect()
    fake["outcome"] = "failed"
    state = _finish(client.post("/api/publish/tiktok", json={"jobId": _export(tmp_path, b"v" * 50)}).json())
    assert state["status"] == "error" and "file_format_check_failed" in state["error"]


def test_posting_needs_an_account_and_a_finished_export(tmp_path, fake):
    assert client.post("/api/publish/tiktok", json={"jobId": "missing"}).status_code in (404, 422)
    assert client.post("/api/publish/tiktok", json={}).status_code == 422
    job = _finish(client.post("/api/publish/tiktok", json={"jobId": _export(tmp_path, b"v" * 50)}).json())
    assert job["status"] == "error" and "Connect a TikTok account" in job["error"]
    _connect()
    assert client.delete("/api/connect/tiktok").json()["connected"] is False
