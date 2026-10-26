"""F5, boot and health (FAMILY_TEST_PLAN layer F5): the engine starts on a free port against an empty
data folder, /api/health answers, and the version it reports is the repository's (F4)."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest
from conftest import ROOT


def get_json(url):
    with urllib.request.urlopen(url, timeout=2) as reply:  # noqa: S310 - the test's own loopback engine
        return reply.status, json.loads(reply.read().decode("utf-8"))


@pytest.fixture(scope="module")
def engine(tmp_path_factory):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    root = tmp_path_factory.mktemp("boot")
    (root / "data").mkdir()
    (root / "home").mkdir()
    env = {
        **os.environ,
        "FORMCUT_DATA_DIR": str(root / "data"),
        "FORMCUT_NO_WARM": "1",
        "FORMCUT_FFMPEG_AUTO": "0",
        "FORMCUT_MODELS_AUTO": "0",
        "HOME": str(root / "home"),
        "USERPROFILE": str(root / "home"),
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT / "backend",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 60
    ready = False
    while time.monotonic() < deadline and process.poll() is None and not ready:
        try:
            ready = get_json(base + "/api/health")[0] == 200
        except OSError:
            time.sleep(0.25)
    if not ready:
        process.kill()
        output = process.communicate(timeout=5)[0].decode("utf-8", "replace")
        raise RuntimeError(f"the engine did not answer /api/health within 60 s:\n{output[-4000:]}")
    yield {"base": base, "process": process, "home": root / "home"}
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()


def test_engine_boots_on_a_free_port_with_an_empty_data_folder(engine):
    status, body = get_json(engine["base"] + "/api/health")
    assert status == 200 and body["status"] == "ok"
    assert engine["process"].poll() is None


def test_engine_reports_the_repository_version(engine):
    manifest = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert get_json(engine["base"] + "/api/health")[1]["version"] == manifest["version"]


def test_engine_keeps_its_files_out_of_the_home_folder(engine):
    assert not [path.name for path in engine["home"].iterdir() if "formcut" in path.name.lower()]
