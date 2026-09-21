"""Upscaling: Lanczos, sharpened Lanczos and bicubic here, and Topaz's Video API."""

import hashlib
import json
import re
import subprocess
import threading
import time
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import pytest
from app import jobs, media, providers, upscale
from app.main import app
from fastapi.testclient import TestClient
from PIL import Image

client = TestClient(app, headers={"x-formcut-local": "1"})


def _clip(tmp_path, name="clip.mp4", size="160x90"):
    path = tmp_path / name
    command = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size={size}:rate=25:duration=1"]
    command += ["-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-c:v", "mpeg4", "-q:v", "3", "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(command, check=True)
    return media.ingest_path(path, name)


def _finish(job, seconds=90):
    deadline = time.time() + seconds
    while time.time() < deadline:
        state = jobs.status(job["job_id"])
        if state["status"] in ("done", "error", "cancelled"):
            return state
        time.sleep(0.1)
    raise AssertionError("the job did not finish")


def _file(record):
    return next(media.MEDIA_DIR.glob(f"{record['id']}.*"))


def _sharpness(path):
    ok, frame = cv2.VideoCapture(str(path)).read()
    assert ok
    return cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()


def test_lanczos_doubles_a_clip_and_keeps_its_sound(tmp_path):
    source = _clip(tmp_path)
    state = _finish(client.post(f"/api/media/{source['id']}/upscale", json={"method": "lanczos", "factor": 2}).json())
    assert state["status"] == "done", state
    result = state["result"]["media"]
    assert (result["width"], result["height"], result["kind"]) == (320, 180, "video")
    assert result["name"] == "clip 2x Lanczos.mp4" and result["upscaledFrom"] == source["id"]
    assert abs(result["duration"] - source["duration"]) < 0.1
    probe = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(_file(result))]
    assert subprocess.run(probe, capture_output=True, text=True, check=True).stdout.split() == ["video", "audio"]


def test_sharpening_adds_edge_contrast(tmp_path):
    source = _clip(tmp_path)
    plain = _finish(client.post(f"/api/media/{source['id']}/upscale", json={"method": "lanczos", "factor": 2}).json())
    sharp = _finish(client.post(f"/api/media/{source['id']}/upscale", json={"method": "sharp", "factor": 2}).json())
    assert _sharpness(_file(sharp["result"]["media"])) > _sharpness(_file(plain["result"]["media"])) * 1.05


def test_a_still_is_upscaled_upright(tmp_path):
    path = tmp_path / "phone.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # stored sideways, shown turned a quarter clockwise
    Image.new("RGB", (40, 20), (200, 40, 40)).save(path, exif=exif)
    source = media.ingest_path(path, "phone.jpg")
    state = _finish(client.post(f"/api/media/{source['id']}/upscale", json={"method": "bicubic", "factor": 2}).json())
    result = state["result"]["media"]
    assert result["name"] == "phone 2x bicubic.png"
    assert Image.open(_file(result)).size == (40, 80)


def test_limits_are_refused_before_any_work(tmp_path):
    wide = tmp_path / "wide.png"
    Image.new("RGB", (3000, 10)).save(wide)
    wide_id = media.ingest_path(wide, "wide.png")["id"]
    sound = tmp_path / "tone.wav"
    with wave.open(str(sound), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(b"\0\0" * 800)
    sound_id = media.ingest_path(sound, "tone.wav")["id"]
    assert client.post(f"/api/media/{wide_id}/upscale", json={"factor": 5}).status_code == 422
    too_wide = client.post(f"/api/media/{wide_id}/upscale", json={"factor": 2})
    assert too_wide.status_code == 422 and "6000" in too_wide.json()["detail"]
    assert client.post(f"/api/media/{sound_id}/upscale", json={"factor": 2}).status_code == 422
    assert client.post(f"/api/media/{wide_id}/upscale", json={"method": "magic"}).status_code == 422


# Topaz, against a fake that follows the documented flow ----------------------


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _reply(self, code, payload=None, headers=None, raw=None):
        body = raw if raw is not None else json.dumps(payload or {}).encode()
        self.send_response(code)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def do_POST(self):
        state = self.server.state
        state["keys"].append(self.headers.get("X-API-Key"))
        state["create"] = json.loads(self._body())
        self._reply(200, {"requestId": "req-1", "estimates": {"cost": [3, 4], "time": [60, 90]}})

    def do_PATCH(self):
        state = self.server.state
        state["keys"].append(self.headers.get("X-API-Key"))
        body = self._body()
        if self.path == "/video/req-1/accept":
            self._reply(200, {"uploadId": "up-1", "urls": [f"{state['base']}/upload/{n}" for n in (1, 2, 3)], "message": "Accepted"})
        else:
            state["complete"] = json.loads(body)
            self._reply(202, {"message": "Processing has been queued"})

    def do_PUT(self):
        state = self.server.state
        number = int(self.path.rsplit("/", 1)[1])
        state["parts"][number] = self._body()
        state["put_keys"].append(self.headers.get("X-API-Key"))
        self._reply(200, headers={"ETag": f'"etag-{number}"'})

    def do_GET(self):
        state = self.server.state
        if self.path == "/download":
            self._reply(200, raw=state["result"])
            return
        if self.path.startswith("/video/00000000"):
            self._reply(404 if self.headers.get("X-API-Key") == "test-key" else 401, {"message": "not found"})
            return
        state["polls"] += 1
        if state["outcome"] == "failed":
            self._reply(200, {"status": "failed", "message": "the source could not be decoded"})
        elif state["polls"] < 2:
            self._reply(200, {"status": "processing", "progress": 50})
        else:
            link = {"url": f"{state['base']}/download", "expiresIn": 86400000}
            self._reply(200, {"status": "complete", "progress": 100, "download": link})


@pytest.fixture
def topaz(tmp_path, monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    result = tmp_path / "result.mp4"
    make = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=25:duration=1", "-c:v", "mpeg4"]
    subprocess.run([*make, str(result)], check=True)
    server.state = {"base": base, "keys": [], "put_keys": [], "parts": {}, "polls": 0, "outcome": "complete", "result": result.read_bytes()}
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(providers, "key_for", lambda name: "test-key")
    monkeypatch.setattr(providers, "base_for", lambda name: base)
    monkeypatch.setattr(upscale, "POLL", 0.01)
    yield server.state
    server.shutdown()


def test_the_estimate_describes_the_clip_and_spends_nothing(tmp_path, topaz):
    source = _clip(tmp_path)
    reply = client.post(f"/api/media/{source['id']}/upscale/estimate", json={"method": "topaz", "factor": 2}).json()
    assert reply == {"request_id": "req-1", "credits": [3, 4], "seconds": [60, 90], "width": 320, "height": 180}
    sent = topaz["create"]
    assert sent["source"]["resolution"] == {"width": 160, "height": 90}
    assert sent["source"]["size"] == _file(source).stat().st_size
    assert sent["source"]["frameCount"] == round(source["duration"] * source["fps"])
    assert sent["output"]["resolution"] == {"width": 320, "height": 180} and sent["filters"][0]["model"] == "prob-4"
    assert topaz["keys"] == ["test-key"] and topaz["parts"] == {}


def test_the_topaz_job_follows_the_documented_steps(tmp_path, topaz):
    source = _clip(tmp_path)
    state = _finish(client.post(f"/api/media/{source['id']}/upscale", json={"method": "topaz", "factor": 2, "request_id": "req-1"}).json())
    assert state["status"] == "done", state
    result = state["result"]["media"]
    assert result["name"] == "clip 2x Topaz prob-4.mp4" and (result["width"], result["height"]) == (320, 180)
    original = _file(source).read_bytes()
    assert b"".join(topaz["parts"][n] for n in (1, 2, 3)) == original
    assert topaz["put_keys"] == [None, None, None]
    assert topaz["complete"] == {
        "uploadResults": [{"partNum": n, "eTag": f"etag-{n}"} for n in (1, 2, 3)],
        "md5Hash": hashlib.md5(original, usedforsecurity=False).hexdigest(),
    }
    assert topaz["polls"] == 2 and set(topaz["keys"]) == {"test-key"}


def test_a_topaz_failure_is_reported_with_its_reason(tmp_path, topaz):
    topaz["outcome"] = "failed"
    source = _clip(tmp_path)
    state = _finish(client.post(f"/api/media/{source['id']}/upscale", json={"method": "topaz", "request_id": "req-1"}).json())
    assert state["status"] == "error" and "could not be decoded" in state["error"]


def test_topaz_needs_an_estimate_first_and_a_key(tmp_path, monkeypatch):
    source = _clip(tmp_path)
    assert client.post(f"/api/media/{source['id']}/upscale", json={"method": "topaz"}).status_code == 422
    monkeypatch.setattr(providers, "key_for", lambda name: "")
    missing = client.post(f"/api/media/{source['id']}/upscale/estimate", json={"method": "topaz"})
    assert missing.status_code == 502 and "No Topaz key" in missing.json()["detail"]


def test_the_key_test_creates_nothing(topaz, monkeypatch):
    assert providers.test_provider("topaz")["ok"] is True
    monkeypatch.setattr(providers, "key_for", lambda name: "wrong")
    refused = providers.test_provider("topaz")
    assert refused["ok"] is False and "rejected" in refused["detail"]
    assert topaz["polls"] == 0 and "create" not in topaz


def test_every_label_the_dialog_shows_is_translated_with_its_placeholders():
    folder = Path(__file__).resolve().parents[1] / "frontend" / "src" / "i18n"
    english = json.loads((folder / "en.json").read_text(encoding="utf-8"))
    rows = [row.split("|") for row in (folder / "language-pack.ts").read_text(encoding="utf-8").split("`")[1].splitlines() if row]
    packed = {row[0]: row[1:] for row in rows}
    keys = [key for key in english if key.startswith("upscale.")] + ["btn.close", "export.cancel", "library.added"]
    assert len(keys) == 21
    for code in ("de", "es"):
        strings = json.loads((folder / f"{code}.json").read_text(encoding="utf-8"))
        assert not [key for key in keys if key not in strings], code
        assert all(set(re.findall(r"\{\w+\}", strings[key])) == set(re.findall(r"\{\w+\}", english[key])) for key in keys), code
    assert not [english[key] for key in keys if english[key] not in packed]
    for key in keys:
        wanted = set(re.findall(r"\{\w+\}", english[key]))
        assert all(set(re.findall(r"\{\w+\}", text)) == wanted for text in packed[english[key]]), key
