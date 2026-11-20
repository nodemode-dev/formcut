"""Starting and stopping: one engine per data folder, a leftover engine is replaced, the engine leaves with its app.

The stand-ins are POSIX programs (`sleep` for an app or an engine, a shell script for the app's program), so the
file skips on Windows. Nothing here has run on Windows.
"""

import json
import os
import subprocess
import sys
import time

import pytest
from conftest import ROOT

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the stand-in programs are POSIX ones")

BACKEND = ROOT / "backend"
FROZEN = "import sys\nsys.frozen = True\nsys.executable = {engine!r}\nsys.argv = ['formcut-engine']\nimport desktop_entry as e\nsys.exit(e.main())\n"
RELEASED = (
    "import datetime, fcntl, json, os, sys, time\n"
    "data = sys.argv[1]\n"
    "held = open(os.path.join(data, 'engine.lock'), 'a+')\n"
    "fcntl.flock(held.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
    "started = datetime.datetime.now(datetime.UTC).isoformat(timespec='seconds')\n"
    "record = {'url': 'http://127.0.0.1:9', 'pid': os.getpid(), 'version': '2.17.0', 'started': started}\n"
    "open(os.path.join(data, 'engine.json'), 'w').write(json.dumps(record))\n"
    "time.sleep(120)\n"
)


def stand_in():
    return subprocess.Popen(["sleep", "120"])


def stop(*procs):
    for proc in procs:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)


def engine_env(data, **more):
    env = {k: v for k, v in os.environ.items() if not k.startswith("FORMCUT_")}
    env.update(FORMCUT_DATA_DIR=str(data), FORMCUT_PORT="0", FORMCUT_NO_WARM="1", PYTHONUNBUFFERED="1", **more)
    return env


def wait_for(check, seconds=60.0):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if check():
            return True
        time.sleep(0.1)
    return False


def published(data):
    try:
        return json.loads((data / "engine.json").read_text())
    except (OSError, ValueError):
        return {}


def record(startup, engine, shell):
    return {
        "pid": engine.pid,
        "started": int(time.time()),
        "born": startup.created(engine.pid),
        "shell": shell.pid,
        "shellBorn": startup.created(shell.pid),
    }


def test_a_holder_whose_shell_is_alive_is_respected(tmp_path):
    from app import startup

    engine, shell, mine = stand_in(), stand_in(), stand_in()
    try:
        (tmp_path / startup.LOCK_NAME).write_text(json.dumps(record(startup, engine, shell)))
        with pytest.raises(startup.Busy) as refused:
            startup.claim(tmp_path, mine.pid)
        assert f"is already running on {tmp_path} (engine process {engine.pid})" in str(refused.value)
        assert engine.poll() is None
    finally:
        stop(engine, shell, mine)


def test_a_holder_whose_shell_is_gone_is_ended_and_replaced(tmp_path):
    from app import startup

    engine, shell, mine = stand_in(), stand_in(), stand_in()
    try:
        (tmp_path / startup.LOCK_NAME).write_text(json.dumps(record(startup, engine, shell)))
        stop(shell)
        path, replaced = startup.claim(tmp_path, mine.pid)
        assert replaced == engine.pid
        assert engine.wait(timeout=10) is not None
        now = json.loads(path.read_text())
        assert now["pid"] == os.getpid() and now["shell"] == mine.pid and now["born"] > 0 and now["shellBorn"] > 0
    finally:
        stop(engine, shell, mine)


def test_a_holder_from_an_engine_that_recorded_no_shell_is_replaced_only_by_an_engine_with_a_shell(tmp_path):
    from app import startup

    engine, mine = stand_in(), stand_in()
    try:
        (tmp_path / startup.LOCK_NAME).write_text(json.dumps({"pid": engine.pid, "started": int(time.time())}))
        with pytest.raises(startup.Busy):
            startup.claim(tmp_path, 0)
        assert engine.poll() is None
        assert startup.claim(tmp_path, mine.pid)[1] == engine.pid
        assert engine.wait(timeout=10) is not None
    finally:
        stop(engine, mine)


@pytest.mark.parametrize("text", ["not json at all", "[1, 2]", '{"pid": "x"}', ""])
def test_a_damaged_record_is_replaced(tmp_path, text):
    from app import startup

    (tmp_path / startup.LOCK_NAME).write_text(text)
    path, replaced = startup.claim(tmp_path, 0)
    assert replaced == 0
    assert json.loads(path.read_text())["pid"] == os.getpid()


def test_a_record_that_names_a_process_which_is_not_the_engine_is_replaced_and_the_process_is_left_alone(tmp_path):
    from app import startup

    other, mine = stand_in(), stand_in()
    try:
        for held in (
            {"pid": other.pid, "started": int(time.time()) - 86400},
            {"pid": other.pid, "started": 5, "born": 12345.5, "shell": 999999, "shellBorn": 5.0},
        ):
            (tmp_path / startup.LOCK_NAME).write_text(json.dumps(held))
            assert startup.claim(tmp_path, mine.pid)[1] == 0
            assert other.poll() is None
        (tmp_path / startup.LOCK_NAME).write_text(json.dumps({"pid": other.pid}))
        with pytest.raises(startup.Busy):
            startup.claim(tmp_path, mine.pid)
        assert other.poll() is None
    finally:
        stop(other, mine)


def test_the_two_ways_of_reading_a_start_time_agree(monkeypatch):
    from app import startup

    first = startup.created(os.getpid())
    monkeypatch.setattr(startup, "PROC", "/nonexistent")
    second = startup.created(os.getpid())
    assert first > 0 and abs(first - second) <= startup.SLACK
    assert startup.created(4_000_000) == 0.0


def test_the_engine_serves_and_keeps_its_errors_with_its_three_streams_closed(tmp_path):
    proc = subprocess.Popen(
        ["/bin/sh", "-c", 'exec "$0" desktop_entry.py <&- >&- 2>&-', sys.executable], cwd=BACKEND, env=engine_env(tmp_path)
    )
    kept = tmp_path / "logs" / "formcut-engine-errors.log"
    try:
        assert wait_for(lambda: kept.is_file() and "Uvicorn running on http://127.0.0.1:" in kept.read_text())
        assert published(tmp_path)["pid"] == proc.pid
        assert any("starting" in log.read_text() for log in (tmp_path / "logs").glob("engine-*.log"))
    finally:
        proc.terminate()
        proc.wait(timeout=30)


def test_the_engine_stops_when_the_app_it_was_given_ends(tmp_path):
    shell = stand_in()
    proc = subprocess.Popen(
        [sys.executable, "desktop_entry.py"],
        cwd=BACKEND,
        env=engine_env(tmp_path, FORMCUT_SHELL_PID=str(shell.pid)),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert wait_for(lambda: published(tmp_path).get("pid") == proc.pid)
        assert json.loads((tmp_path / "engine.owner").read_text())["shell"] == shell.pid
        stop(shell)
        assert proc.wait(timeout=10) == 0
        assert not (tmp_path / "engine.owner").exists() and not (tmp_path / "engine.json").exists()
    finally:
        stop(shell, proc)


def test_a_second_engine_is_refused_while_the_first_ones_app_lives(tmp_path):
    first, second = stand_in(), stand_in()
    env = engine_env(tmp_path, FORMCUT_SHELL_PID=str(first.pid))
    proc = subprocess.Popen(
        [sys.executable, "desktop_entry.py"], cwd=BACKEND, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    try:
        assert wait_for(lambda: published(tmp_path).get("pid") == proc.pid)
        env = engine_env(tmp_path, FORMCUT_SHELL_PID=str(second.pid))
        done = subprocess.run(
            [sys.executable, "desktop_entry.py"], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60, check=False
        )
        assert done.returncode == 2
        assert f"formcut is already running on {tmp_path} (engine process {proc.pid})." in done.stderr
        assert proc.poll() is None and json.loads((tmp_path / "engine.owner").read_text())["pid"] == proc.pid
    finally:
        stop(first, second)
        proc.wait(timeout=10)


def test_an_engine_from_before_the_record_is_replaced_only_by_an_engine_with_an_app(tmp_path):
    shell = stand_in()
    old = subprocess.Popen([sys.executable, "-c", RELEASED, str(tmp_path)])
    proc = None
    try:
        assert wait_for(lambda: published(tmp_path).get("pid") == old.pid)
        done = subprocess.run(
            [sys.executable, "desktop_entry.py"],
            cwd=BACKEND,
            env=engine_env(tmp_path),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert done.returncode == 2
        assert f"formcut is already running on {tmp_path} (engine process {old.pid})." in done.stderr
        assert old.poll() is None and not (tmp_path / "engine.owner").exists()
        proc = subprocess.Popen(
            [sys.executable, "desktop_entry.py"],
            cwd=BACKEND,
            env=engine_env(tmp_path, FORMCUT_SHELL_PID=str(shell.pid)),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert wait_for(lambda: published(tmp_path).get("pid") == proc.pid)
        assert old.wait(timeout=10) is not None
        assert json.loads((tmp_path / "engine.owner").read_text())["pid"] == proc.pid
    finally:
        stop(shell, old)
        if proc is not None:
            proc.wait(timeout=10)


def test_a_frozen_engine_started_alone_opens_the_app_beside_it_and_serves_nothing(tmp_path):
    install, data, mark = tmp_path / "install", tmp_path / "data", tmp_path / "opened"
    install.mkdir()
    data.mkdir()
    app = install / "formcut"
    app.write_text(f'#!/bin/sh\nprintf "%s" "$(pwd)" > "{mark}"\n')
    app.chmod(0o755)
    code = FROZEN.format(engine=str(install / "formcut-engine"))
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, env=engine_env(data), capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode == 0, done.stderr
    assert wait_for(mark.is_file, 10)
    assert mark.read_text() == str(install.resolve())
    assert not (data / "engine.owner").exists() and not (data / "engine.json").exists()
    assert any("started without its app" in log.read_text() for log in (data / "logs").glob("engine-*.log"))


def test_a_frozen_engine_started_alone_with_no_app_near_it_says_so_and_serves_nothing(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    code = FROZEN.format(engine=str(tmp_path / "engine" / "formcut-engine"))
    done = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, env=engine_env(data), capture_output=True, text=True, timeout=60, check=False
    )
    assert done.returncode == 4
    assert "serves nothing on its own" in done.stderr
    assert not (data / "engine.owner").exists()
