"""The proxy controls the window offers: the settings switch and size, and Make or Rebuild on a media card.

The settings are kept in the data folder, so a choice made in Settings holds after the engine restarts; a size chosen
there is the one a proxy is built at when the card, the import or an agent asks for one without naming a size; and
with proxies switched off, an import builds none.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest
from app import automation, media, proxies
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app, headers={"x-formcut-local": "1"})
needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg to make a clip")


@pytest.fixture(autouse=True)
def own_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(proxies, "SETTINGS_PATH", tmp_path / "proxy-settings.json")
    monkeypatch.setattr(proxies, "EARLIER_SETTINGS_PATH", tmp_path / "proxies" / "settings.json")
    monkeypatch.setattr(proxies, "_settings", None)
    return tmp_path / "proxy-settings.json"


@pytest.fixture
def queued(monkeypatch):
    asked = []
    monkeypatch.setattr(
        proxies, "enqueue", lambda media_id, source, long_side=None: asked.append((media_id, long_side)) or {"state": "queued"}
    )
    return asked


@pytest.fixture(scope="module")
def video_id(tmp_path_factory):
    if not shutil.which("ffmpeg"):
        pytest.skip("needs ffmpeg to make a clip")
    clip = tmp_path_factory.mktemp("proxy-controls") / "clip.mp4"
    command = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=25:duration=1", "-c:v", "mpeg4", str(clip)]
    subprocess.run(command, check=True)
    return media.ingest_path(clip, "clip.mp4")["id"]


def test_the_settings_start_on_at_the_default_size():
    assert client.get("/api/proxies/settings").json() == {"enabled": True, "size": proxies.DEFAULT_LONG_SIDE, "sizes": [960, 1280, 1920]}


def test_a_change_is_kept_in_the_data_folder_and_read_back_after_a_restart(own_settings, monkeypatch):
    assert client.post("/api/proxies/settings", json={"enabled": False}).json()["enabled"] is False
    assert client.post("/api/proxies/settings", json={"size": 1920}).json() == {"enabled": False, "size": 1920, "sizes": [960, 1280, 1920]}
    assert own_settings.is_file()
    monkeypatch.setattr(proxies, "_settings", None)
    assert client.get("/api/proxies/settings").json()["enabled"] is False
    assert proxies.chosen_size() == 1920


@pytest.mark.parametrize(
    "body",
    [{"size": 1000}, {"size": "1280"}, {"enabled": "false"}, {"enabled": 0}, {"colour": True}],
    ids=["unknown-size", "size-as-text", "switch-as-text", "switch-as-number", "unknown-field"],
)
def test_a_setting_that_is_not_one_is_refused_and_changes_nothing(body):
    assert client.post("/api/proxies/settings", json=body).status_code == 422
    assert client.get("/api/proxies/settings").json()["enabled"] is True
    assert proxies.chosen_size() == proxies.DEFAULT_LONG_SIDE


def test_a_damaged_settings_file_falls_back_to_the_defaults(own_settings):
    own_settings.write_text('{"enabled": "no", "size": 77', encoding="utf-8")
    assert proxies.settings() == {"enabled": True, "size": proxies.DEFAULT_LONG_SIDE, "sizes": [960, 1280, 1920]}


@needs_ffmpeg
def test_make_proxy_builds_at_the_size_chosen_in_settings(video_id, queued):
    client.post("/api/proxies/settings", json={"size": 960})
    reply = client.post(f"/api/media/{video_id}/proxy")
    assert reply.status_code == 202
    assert queued == [(video_id, 960)]


@needs_ffmpeg
def test_make_proxy_takes_a_size_it_is_given_and_refuses_an_unknown_one(video_id, queued):
    assert client.post(f"/api/media/{video_id}/proxy?size=1920").status_code == 202
    assert client.post(f"/api/media/{video_id}/proxy?size=1000").status_code == 422
    assert queued == [(video_id, 1920)]


def test_make_proxy_refuses_media_that_is_not_video(tmp_path, queued):
    import wave

    sound = tmp_path / "tone.wav"
    with wave.open(str(sound), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.writeframes(b"\0\0" * 800)
    sound_id = media.ingest_path(sound, "tone.wav")["id"]
    assert client.post(f"/api/media/{sound_id}/proxy").status_code == 400
    assert queued == []


@needs_ffmpeg
def test_a_rebuild_queues_a_new_build_over_a_ready_proxy(video_id, monkeypatch):
    from queue import Queue

    work = Queue()
    monkeypatch.setattr(proxies, "_ensure_worker", lambda: None)
    monkeypatch.setattr(proxies, "_work", work)
    monkeypatch.setattr(proxies, "_queued", {})
    monkeypatch.setattr(proxies, "status", lambda media_id, source=None: {"state": "ready"})
    reply = client.post(f"/api/media/{video_id}/proxy")
    assert reply.json() == {"state": "queued", "progress": 0.0}
    assert proxies._queued == {video_id: proxies.DEFAULT_LONG_SIDE}
    assert work.get_nowait()[::2] == (video_id, proxies.DEFAULT_LONG_SIDE)


@needs_ffmpeg
@pytest.mark.parametrize("switched_on", [True, False], ids=["on", "off"])
def test_an_import_builds_a_proxy_only_while_proxies_are_on(tmp_path, queued, monkeypatch, switched_on):
    monkeypatch.setattr(proxies, "wants_proxy", lambda item: True)
    client.post("/api/proxies/settings", json={"enabled": switched_on})
    clip = tmp_path / "heavy.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=25:duration=1", "-c:v", "mpeg4", str(clip)],
        check=True,
    )
    media_id = media.ingest_path(clip, "heavy.mp4")["id"]
    assert queued == ([(media_id, None)] if switched_on else [])


@needs_ffmpeg
def test_the_agent_tools_build_flag_builds(video_id, queued):
    """formcut_media_proxy sends build=true; the RPC read only "action", so the tool said queued and nothing was."""
    automation.dispatch("media.proxy", {"id": video_id, "build": True})
    assert queued == [(video_id, proxies.DEFAULT_LONG_SIDE)]
    automation.dispatch("media.proxy", {"id": video_id})
    assert len(queued) == 1


def test_the_preview_reads_a_proxy_only_while_proxies_are_on(monkeypatch):
    from app import renderer

    client.post("/api/proxies/settings", json={"enabled": False})
    assert renderer.proxies_enabled() is False
    client.post("/api/proxies/settings", json={"enabled": True})
    assert renderer.proxies_enabled() is True
