"""Webhooks: signed deliveries when an export finishes."""

import hashlib
import hmac
import json
import threading
import time
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from app import jobs, render_api, webhooks
from app.main import APP_VERSION, app
from fastapi.testclient import TestClient

client = TestClient(app, headers={"x-formcut-local": "1"})


class Receiver(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def do_POST(self):
        state = self.server.state
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        state["requests"].append({"headers": dict(self.headers), "body": body})
        code = state["codes"].pop(0) if state["codes"] else 200
        self.send_response(code)
        if code == 302:
            self.send_header("Location", "https://elsewhere.example/")
        self.send_header("Content-Length", "0")
        self.end_headers()


@pytest.fixture
def receiver(tmp_path, monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    server.state = {"requests": [], "codes": [], "url": f"http://127.0.0.1:{server.server_address[1]}/hook"}
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(webhooks, "STORE", tmp_path / "webhooks.json")
    monkeypatch.setattr(webhooks, "RETRIES", (0.0, 0.0, 0.0))
    yield server.state
    server.shutdown()


def _verified(secret, request, body):
    """What a receiver does: recompute the signature over timestamp, '.', body."""
    timestamp = request["headers"]["X-Formcut-Timestamp"]
    expected = "sha256=" + hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, request["headers"]["X-Formcut-Signature"])


def _wait(predicate, seconds=10.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _export(tmp_path, content=b"x" * 1000):
    video = tmp_path / "cut.mp4"
    video.write_bytes(content)
    return {
        "file": str(video),
        "name": "formcut-export.mp4",
        "media_type": "video/mp4",
        "width": 1920,
        "height": 1080,
        "frames": 250,
        "codec": "h264",
    }


def test_a_webhook_is_added_listed_changed_and_removed(receiver):
    hook = client.post("/api/webhooks", json={"url": receiver["url"]}).json()
    assert (hook["url"], hook["sendFile"], hook["enabled"], hook["last"]) == (receiver["url"], False, True, None)
    assert len(hook["secret"]) == 48
    assert client.get("/api/webhooks").json() == [hook]
    assert client.patch(f"/api/webhooks/{hook['id']}", json={"sendFile": True}).json()["sendFile"] is True
    assert client.delete(f"/api/webhooks/{hook['id']}").json() == {"removed": hook["id"]}
    assert client.get("/api/webhooks").json() == []
    assert client.delete(f"/api/webhooks/{hook['id']}").status_code == 404


def test_addresses_that_are_not_web_addresses_are_refused(receiver):
    for address in ("ftp://example.com/hook", "example.com/hook", "javascript:alert(1)", "https://"):
        assert client.post("/api/webhooks", json={"url": address}).status_code == 422, address


def test_a_test_ping_is_signed_and_its_outcome_kept(receiver):
    hook = client.post("/api/webhooks", json={"url": receiver["url"]}).json()
    outcome = client.post(f"/api/webhooks/{hook['id']}/test").json()
    assert (outcome["status"], outcome["attempts"], outcome["code"]) == ("delivered", 1, 200)
    request = receiver["requests"][0]
    payload = json.loads(request["body"])
    assert (payload["event"], payload["app"]) == ("ping", {"name": "formcut", "version": APP_VERSION})
    assert request["headers"]["X-Formcut-Event"] == "ping" and request["headers"]["X-Formcut-Delivery"] == payload["id"]
    assert _verified(hook["secret"], request, request["body"])
    assert not _verified(hook["secret"], request, request["body"].replace(b"ping", b"pong"))
    assert client.get("/api/webhooks").json()[0]["last"]["status"] == "delivered"


def test_an_export_is_announced_with_its_details(tmp_path, receiver):
    hook = client.post("/api/webhooks", json={"url": receiver["url"]}).json()
    for thread in webhooks.announce_export(_export(tmp_path), {"name": "Holiday"}):
        thread.join(10)
    request = receiver["requests"][0]
    payload = json.loads(request["body"])
    assert payload["event"] == "export.finished" and request["headers"]["Content-Type"] == "application/json"
    assert payload["export"] == {
        "name": "formcut-export.mp4",
        "mediaType": "video/mp4",
        "bytes": 1000,
        "sha256": hashlib.sha256(b"x" * 1000).hexdigest(),
        "width": 1920,
        "height": 1080,
        "frames": 250,
        "codec": "h264",
        "project": "Holiday",
    }
    assert _verified(hook["secret"], request, request["body"])


def test_the_video_itself_can_go_too(tmp_path, receiver):
    hook = client.post("/api/webhooks", json={"url": receiver["url"], "sendFile": True}).json()
    content = bytes(range(256)) * 40
    for thread in webhooks.announce_export(_export(tmp_path, content)):
        thread.join(10)
    request = receiver["requests"][0]
    raw = b"Content-Type: " + request["headers"]["Content-Type"].encode() + b"\r\n\r\n" + request["body"]
    message = BytesParser(policy=default).parsebytes(raw)
    parts = {part.get_param("name", header="content-disposition"): part for part in message.iter_parts()}
    payload = parts["payload"].get_content()
    assert parts["file"].get_content() == content and parts["file"].get_filename() == "cut.mp4"
    assert json.loads(payload)["export"]["sha256"] == hashlib.sha256(content).hexdigest()
    assert _verified(hook["secret"], request, payload.encode())


def test_failures_that_may_pass_are_retried(receiver):
    hook = client.post("/api/webhooks", json={"url": receiver["url"]}).json()
    receiver["codes"] = [500, 503]
    outcome = webhooks.deliver(webhooks._find(hook["id"]), "ping", {})
    assert (outcome["status"], outcome["attempts"]) == ("delivered", 3)
    receiver["codes"] = [500, 500, 500, 500]
    outcome = webhooks.deliver(webhooks._find(hook["id"]), "ping", {})
    assert (outcome["status"], outcome["attempts"], outcome["detail"]) == ("failed", 4, "HTTP 500")


def test_a_refusal_is_final_and_redirects_are_not_followed(receiver):
    hook = client.post("/api/webhooks", json={"url": receiver["url"]}).json()
    receiver["codes"] = [404]
    refused = webhooks.deliver(webhooks._find(hook["id"]), "ping", {})
    assert (refused["status"], refused["attempts"], refused["detail"]) == ("failed", 1, "HTTP 404")
    receiver["codes"] = [302]
    moved = webhooks.deliver(webhooks._find(hook["id"]), "ping", {})
    assert (moved["status"], moved["attempts"]) == ("failed", 1) and "not followed" in moved["detail"]
    assert len(receiver["requests"]) == 2


def test_a_disabled_webhook_hears_nothing(tmp_path, receiver):
    hook = client.post("/api/webhooks", json={"url": receiver["url"]}).json()
    client.patch(f"/api/webhooks/{hook['id']}", json={"enabled": False})
    assert webhooks.announce_export(_export(tmp_path)) == []
    assert receiver["requests"] == []


def test_the_export_route_announces_what_it_made(tmp_path, receiver, monkeypatch):
    client.post("/api/webhooks", json={"url": receiver["url"]})
    result = _export(tmp_path)
    monkeypatch.setattr(render_api, "checked", lambda body: {"name": "Holiday"})
    monkeypatch.setattr(render_api, "export_media", lambda *args: result)
    job = client.post("/api/render/export", json={"project": {}}).json()
    assert _wait(lambda: jobs.status(job["job_id"])["status"] == "done")
    assert _wait(lambda: receiver["requests"])
    payload = json.loads(receiver["requests"][0]["body"])
    assert (payload["event"], payload["export"]["project"], payload["export"]["bytes"]) == ("export.finished", "Holiday", 1000)


FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "src"


def test_settings_has_a_key_panel_for_every_stock_speech_and_upscale_provider():
    from app.providers import PROVIDERS

    panels = (FRONTEND / "ui" / "settings-popout.ts").read_text(encoding="utf-8")
    listed = {name for name, spec in PROVIDERS.items() if spec["purpose"] in ("stock", "speech", "upscale")}
    assert listed == {"pexels", "elevenlabs", "topaz"}
    assert all(f'["{name}", "{PROVIDERS[name]["label"]}"]' in panels for name in listed)


def test_every_settings_label_for_topaz_and_webhooks_is_translated():
    english = json.loads((FRONTEND / "i18n" / "en.json").read_text(encoding="utf-8"))
    rows = (FRONTEND / "i18n" / "language-pack.ts").read_text(encoding="utf-8").split("`")[1].splitlines()
    packed = {row.split("|")[0] for row in rows if row}
    keys = ["prov.topaz.use", "prov.test", "prov.testing", *(key for key in english if key.startswith("hooks."))]
    assert len(keys) == 16
    for code in ("de", "es"):
        strings = json.loads((FRONTEND / "i18n" / f"{code}.json").read_text(encoding="utf-8"))
        assert not [key for key in keys if key not in strings], code
    assert not [english[key] for key in keys if english[key] not in packed]
