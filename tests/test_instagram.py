"""Instagram: Reels through Meta's resumable upload, against a fake that follows Meta's documentation."""

import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest
from app import instagram, jobs
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app, headers={"x-formcut-local": "1"})


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

    def do_GET(self):
        state = self.server.state
        url = urlsplit(self.path)
        given = parse_qs(url.query).get("access_token", [""])[0]
        if given == "bad":
            self._reply(400, {"error": {"message": "Invalid OAuth access token", "code": 190}})
        elif url.path == "/v25.0/me/accounts":
            pages = [{"id": "page1"}, {"id": "page2", "instagram_business_account": {"id": "1784", "username": "maker"}}]
            self._reply(200, {"data": pages if given == "user-token" else []})
        elif url.path == "/v25.0/me":
            own = {"instagram_business_account": {"id": "1785", "username": "pagemaker"}} if given == "page-token" else {}
            self._reply(200, {"id": "me", **own})
        else:
            state["polls"] += 1
            finished = "FINISHED" if state["polls"] >= 2 else "IN_PROGRESS"
            self._reply(200, {"id": "c1", "status_code": "ERROR" if state["outcome"] == "error" else finished})

    def do_POST(self):
        state = self.server.state
        raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path.startswith("/ig-api-upload/"):
            state["upload"] = {"path": self.path, "headers": dict(self.headers), "body": raw}
            self._reply(200, {"success": True, "message": "Upload successful."})
            return
        form = {key: values[0] for key, values in parse_qs(raw.decode()).items()}
        state["posts"].append((self.path, form))
        if self.path.endswith("/media"):
            self._reply(200, {"id": "c1", "uri": f"{state['base']}/ig-api-upload/v25.0/c1"})
        else:
            self._reply(200, {"id": "m1"})


@pytest.fixture
def meta(tmp_path, monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    server.state = {"base": base, "posts": [], "polls": 0, "outcome": "ok"}
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(instagram, "STORE", tmp_path / "instagram.json")
    monkeypatch.setattr(instagram, "POLL", 0.01)
    monkeypatch.setenv("INSTAGRAM_GRAPH_BASE", base)
    yield server.state
    server.shutdown()


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


def test_a_user_token_finds_the_account_through_its_pages(meta):
    shown = client.put("/api/connect/instagram", json={"token": "user-token"}).json()
    assert shown == {"connected": True, "userId": "1784", "username": "maker"}
    assert "user-token" not in json.dumps(client.get("/api/connect/instagram").json())
    assert os.stat(instagram.STORE).st_mode & 0o777 == 0o600


def test_a_page_token_finds_its_own_account(meta):
    assert client.put("/api/connect/instagram", json={"token": "page-token"}).json()["userId"] == "1785"


def test_a_token_without_an_account_or_an_invalid_one_is_refused(meta):
    lonely = client.put("/api/connect/instagram", json={"token": "lonely-token"})
    assert lonely.status_code == 422 and "No Instagram professional account" in lonely.json()["detail"]
    invalid = client.put("/api/connect/instagram", json={"token": "bad"})
    assert invalid.status_code == 422 and "Invalid OAuth access token" in invalid.json()["detail"]
    assert client.get("/api/connect/instagram").json()["connected"] is False


def test_a_reel_follows_the_resumable_steps(tmp_path, meta, monkeypatch):
    client.put("/api/connect/instagram", json={"token": "user-token"})
    monkeypatch.setattr(instagram, "codec", lambda path: "h264")
    content = bytes(range(256)) * 8
    job = client.post("/api/publish/instagram", json={"jobId": _export(tmp_path, content), "caption": "Beach day"}).json()
    state = _finish(job)
    assert state["status"] == "done" and state["result"] == {"mediaId": "m1", "containerId": "c1"}
    path, form = meta["posts"][0]
    assert path == "/v25.0/1784/media"
    expected = {"media_type": "REELS", "upload_type": "resumable", "caption": "Beach day", "share_to_feed": "true"}
    assert form == {**expected, "access_token": "user-token"}
    upload = meta["upload"]
    assert upload["path"] == "/ig-api-upload/v25.0/c1" and upload["body"] == content
    sent = upload["headers"]
    assert (sent["Authorization"], sent["offset"], sent["file_size"]) == ("OAuth user-token", "0", str(len(content)))
    assert meta["posts"][1] == ("/v25.0/1784/media_publish", {"creation_id": "c1", "access_token": "user-token"})
    assert meta["polls"] == 2


def test_a_video_that_is_not_h264_or_hevc_is_refused_before_anything_is_sent(tmp_path, meta):
    client.put("/api/connect/instagram", json={"token": "user-token"})
    clip = tmp_path / "part2.mp4"
    make = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=25:duration=1", "-c:v", "mpeg4"]
    subprocess.run([*make, str(clip)], check=True)
    job_id = _export(tmp_path, clip.read_bytes())
    refused = client.post("/api/publish/instagram", json={"jobId": job_id})
    assert refused.status_code == 422 and "mpeg4" in refused.json()["detail"] and "H.264" in refused.json()["detail"]
    assert meta["posts"] == []


def test_an_error_status_is_reported_and_nothing_is_published(tmp_path, meta, monkeypatch):
    client.put("/api/connect/instagram", json={"token": "user-token"})
    monkeypatch.setattr(instagram, "codec", lambda path: "hevc")
    meta["outcome"] = "error"
    state = _finish(client.post("/api/publish/instagram", json={"jobId": _export(tmp_path, b"v" * 64)}).json())
    assert state["status"] == "error" and "ERROR" in state["error"]
    assert [path for path, _ in meta["posts"]] == ["/v25.0/1784/media"]


def test_posting_needs_an_account_and_disconnecting_forgets_the_token(tmp_path, meta):
    assert client.post("/api/publish/instagram", json={"jobId": "x"}).status_code == 409
    client.put("/api/connect/instagram", json={"token": "user-token"})
    assert client.delete("/api/connect/instagram").json()["connected"] is False
    assert "user-token" not in instagram.STORE.read_text()


def _i18n(name):
    with open(os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "i18n", name), encoding="utf-8") as handle:
        return handle.read()


def test_every_instagram_label_is_translated_and_keeps_its_placeholder():
    english = json.loads(_i18n("en.json"))
    rows = _i18n("language-pack.ts").split("`")[1].splitlines()
    packed = {row.split("|")[0]: row.split("|")[1:] for row in rows if row}
    keys = [key for key in english if key.startswith("instagram.")] + ["prov.instagram.use"]
    assert len(keys) == 13
    for code in ("de", "es"):
        strings = json.loads(_i18n(f"{code}.json"))
        assert not [key for key in keys if key not in strings], code
        assert "{name}" in strings["instagram.as"], code
    assert not [english[key] for key in keys if english[key] not in packed]
    assert all("{name}" in text for text in packed[english["instagram.as"]])
