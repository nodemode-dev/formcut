"""Pocket TTS and Chatterbox beside Kokoro.

Both engines live in the speech runtime, never the frozen engine, so most of
this checks the routing: which engine is asked, what is refused and why. The
last test runs the real thing when a speech runtime with Pocket TTS is named in
FORMCUT_TEST_SPEECH_PYTHON: text in, a voice in the library out.
"""

import ast
import os
import subprocess
import time
from pathlib import Path

import pytest
from app import jobs, local_speech
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def fresh_probes():
    local_speech._runtime.clear()
    yield
    local_speech._runtime.clear()


def test_the_three_engines_are_listed_with_their_licences():
    listed = {e["id"]: e for e in local_speech.engines()}
    assert set(listed) == {"kokoro", "pocket", "chatterbox"}
    assert "CC-BY-4.0" in listed["pocket"]["license"] and "watermark" in listed["chatterbox"]["license"]


def test_without_a_runtime_pocket_offers_its_documented_voices(monkeypatch):
    monkeypatch.setattr(local_speech, "runtime", lambda: None)
    voices = local_speech.voices("pocket")
    assert not voices["installed"] and [v["id"] for v in voices["voices"]] == local_speech.POCKET_VOICES


def _speak(**fields):
    return local_speech.speak(local_speech.SpeechInput(text="Hello there.", **fields))


def test_an_unknown_engine_is_refused():
    with pytest.raises(HTTPException) as refused:
        _speak(engine="nope")
    assert refused.value.status_code == 422


def test_an_engine_that_is_not_installed_says_so(monkeypatch):
    monkeypatch.setattr(local_speech, "runtime", lambda: "/usr/bin/python3")
    monkeypatch.setattr(local_speech, "installed", lambda engine: False)
    with pytest.raises(HTTPException, match="Install Chatterbox first"):
        _speak(engine="chatterbox")


def test_cloning_a_voice_needs_the_speakers_permission(monkeypatch):
    monkeypatch.setattr(local_speech, "runtime", lambda: "/usr/bin/python3")
    monkeypatch.setattr(local_speech, "installed", lambda engine: True)
    with pytest.raises(HTTPException, match="permission"):
        _speak(engine="pocket", reference="some-media", consent=False)


def test_pocket_refuses_a_voice_it_does_not_have(monkeypatch):
    monkeypatch.setattr(local_speech, "runtime", lambda: "/usr/bin/python3")
    monkeypatch.setattr(local_speech, "installed", lambda engine: True)
    monkeypatch.setattr(local_speech, "pocket_voices", lambda: ["alba"])
    with pytest.raises(HTTPException, match="no voice by that name"):
        _speak(engine="pocket", voice="nobody")


def test_only_the_two_package_engines_install():
    with pytest.raises(HTTPException) as refused:
        local_speech.install("kokoro")
    assert refused.value.status_code == 404


def test_the_workers_are_valid_python_and_chatterbox_speaks_the_panels_languages():
    for worker in (local_speech.POCKET_WORKER, local_speech.CHATTERBOX_WORKER):
        ast.parse(worker)
    assert local_speech.CHATTERBOX_LANGUAGES["cmn"] == "zh" and local_speech.CHATTERBOX_LANGUAGES["fr-fr"] == "fr"


def test_a_speech_worker_does_not_inherit_opencvs_library_path(monkeypatch):
    engine_libs = str(Path("/engine/site-packages/cv2/../../lib64"))
    monkeypatch.setenv("LD_LIBRARY_PATH", os.pathsep.join([engine_libs, "/opt/own/lib"]))
    assert local_speech._worker_env()["LD_LIBRARY_PATH"] == "/opt/own/lib"
    monkeypatch.setenv("LD_LIBRARY_PATH", engine_libs)
    assert "LD_LIBRARY_PATH" not in local_speech._worker_env()


SPEECH_PYTHON = os.environ.get("FORMCUT_TEST_SPEECH_PYTHON")


def _has_pocket(python):
    return bool(python) and subprocess.run([python, "-c", "import pocket_tts"], capture_output=True, check=False).returncode == 0


@pytest.mark.skipif(not _has_pocket(SPEECH_PYTHON), reason="needs a speech runtime with pocket-tts in FORMCUT_TEST_SPEECH_PYTHON")
def test_pocket_speaks_into_the_library(monkeypatch):
    monkeypatch.setenv("FORMCUT_AI_PYTHON", SPEECH_PYTHON)
    cache = os.environ.get("FORMCUT_TEST_HF_HOME")
    if cache:
        clean = local_speech._worker_env
        monkeypatch.setattr(local_speech, "_worker_env", lambda: {**clean(), "HF_HOME": cache})
    assert len(local_speech.pocket_voices()) > len(local_speech.POCKET_VOICES)
    job = _speak(engine="pocket", voice="alba")
    deadline = time.time() + 600
    while (state := jobs.status(job["job_id"]))["status"] in ("queued", "running") and time.time() < deadline:
        time.sleep(0.5)
    assert state["status"] == "done", state
    media = state["result"]["media"]
    assert media["duration"] > 0.5 and media["kind"] == "audio"
    assert any(Path(os.environ["FORMCUT_DATA_DIR"]).rglob(f"{media['id']}.*"))
