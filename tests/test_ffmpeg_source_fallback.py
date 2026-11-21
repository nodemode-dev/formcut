"""The FFmpeg source fetch, against a local stand-in for ffmpeg.org and the family copy at dl.formai.studio.

Each address is checked on its own: a wrong SHA-256 from the first is removed and the second is tried, and only when
no address gives the pinned bytes does the fetch stop, with nothing kept. Run for setup/ffmpeg_source (which
setup/build_lgpl_av uses) and for its Windows twin, setup/build_lgpl_ffmpeg_msvc.
"""

import hashlib
import http.server
import os
import shutil
import subprocess
import sys
import threading

import pytest
from conftest import ROOT

pytestmark = pytest.mark.skipif(sys.platform == "win32" or not shutil.which("curl"), reason="runs the bash scripts")

RIGHT, WRONG = b"the pinned ffmpeg source", b"something else"
SHA = hashlib.sha256(RIGHT).hexdigest()
NAME = "ffmpeg-9.9.tar.xz"


@pytest.fixture
def addresses(tmp_path):
    served = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            body = served.get(self.path)
            if body is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    stubs = tmp_path / "bin"
    stubs.mkdir()
    # curl is the real one, with the two public addresses pointed at the stand-in
    (stubs / "curl").write_text(
        '#!/usr/bin/env bash\nargs=()\nfor a in "$@"; do\n'
        f'  a="${{a/https:\\/\\/ffmpeg.org\\/releases/http://127.0.0.1:{port}/first}}"\n'
        f'  a="${{a/https:\\/\\/dl.formai.studio\\/sources\\/ffmpeg/http://127.0.0.1:{port}/second}}"\n'
        f'  args+=("$a")\ndone\nexec {shutil.which("curl")} --retry 0 --max-time 20 "${{args[@]}}"\n'
    )
    for name, body in (("pacman", "exit 0"), ("cygpath", 'echo "${@: -1}"'), ("link", "exit 0")):
        (stubs / name).write_text(f"#!/usr/bin/env bash\n{body}\n")
    for stub in stubs.iterdir():
        stub.chmod(0o755)

    def publish(first, second):
        served.clear()
        for where, body in (("first", first), ("second", second)):
            if body is not None:
                served[f"/{where}/{NAME}"] = body

    yield publish, stubs
    server.shutdown()


def _source(tmp_path, stubs):
    setup = tmp_path / "setup"
    setup.mkdir()
    shutil.copy(ROOT / "setup" / "ffmpeg_source", setup)
    (setup / "build_lgpl_av").write_text(f"FFMPEG_VERSION=9.9\nFFMPEG_SHA256={SHA}\n")
    run = subprocess.run(
        ["bash", str(setup / "ffmpeg_source"), str(tmp_path / "out")],
        env={**os.environ, "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return run, tmp_path / "out" / NAME


def _windows(tmp_path, stubs):
    work = tmp_path / "work"
    work.mkdir()
    run = subprocess.run(
        ["bash", str(ROOT / "setup" / "build_lgpl_ffmpeg_msvc"), str(stubs), str(work), str(tmp_path / "prefix"), "9.9", SHA],
        env={**os.environ, "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return run, work / NAME


@pytest.mark.parametrize("fetch", [_source, _windows], ids=["ffmpeg_source", "build_lgpl_ffmpeg_msvc"])
def test_a_wrong_hash_from_the_first_address_is_removed_and_the_second_is_used(addresses, tmp_path, fetch):
    publish, stubs = addresses
    publish(WRONG, RIGHT)
    run, kept = fetch(tmp_path, stubs)
    said = run.stdout + run.stderr
    assert f"https://ffmpeg.org/releases/{NAME} gave a {NAME} with the wrong SHA-256, so it was removed" in said
    assert kept.read_bytes() == RIGHT
    assert "no address gave" not in said


@pytest.mark.parametrize("fetch", [_source, _windows], ids=["ffmpeg_source", "build_lgpl_ffmpeg_msvc"])
def test_a_wrong_hash_from_both_addresses_stops_and_keeps_nothing(addresses, tmp_path, fetch):
    publish, stubs = addresses
    publish(WRONG, WRONG)
    run, kept = fetch(tmp_path, stubs)
    said = run.stdout + run.stderr
    assert run.returncode == 1
    assert "ffmpeg.org/releases" in said and "dl.formai.studio/sources/ffmpeg" in said
    assert f"no address gave a {NAME} with the expected SHA-256 (ffmpeg.org, dl.formai.studio); nothing was kept" in said
    assert not kept.exists()


@pytest.mark.parametrize("fetch", [_source, _windows], ids=["ffmpeg_source", "build_lgpl_ffmpeg_msvc"])
def test_a_first_address_that_is_down_moves_on_to_the_second(addresses, tmp_path, fetch):
    publish, stubs = addresses
    publish(None, RIGHT)
    run, kept = fetch(tmp_path, stubs)
    assert f"https://ffmpeg.org/releases/{NAME} did not answer" in run.stdout + run.stderr
    assert kept.read_bytes() == RIGHT
