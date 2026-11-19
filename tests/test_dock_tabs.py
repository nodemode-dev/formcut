"""Terminal tabs by id, agent status and the consent fields, for the shared dock.

A plain shell tab carries no tab token; each Claude Code, Codex and Cursor tab
carries its own, in its environment and never on a command line, and the token
is refused once the tab is closed. The stand-in programs here are scripts in a
temporary folder: no real agent program is started.
"""

import json
import os
import stat
import subprocess
import threading
import time
from pathlib import Path

import pytest
from app import agent_access, dock_tabs, extensions, terminal
from app.main import app
from conftest import bare as as_any_program
from conftest import window_headers
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(os.name != "posix", reason="the stand-in programs are shell scripts on a pseudo-terminal")

OWN = "http://127.0.0.1:8123"
LOCAL = {"x-formcut-local": "1"}
PROGRAMS = {"claude": "claude", "codex": "codex", "cursor": "cursor-agent"}


@pytest.fixture(scope="module")
def bare():
    return as_any_program(TestClient(app, base_url=OWN))


@pytest.fixture(scope="module")
def window():
    return TestClient(app, base_url=OWN, headers=window_headers())


@pytest.fixture
def stored_choice():
    agent_access.STORE.unlink(missing_ok=True)
    yield
    agent_access.STORE.unlink(missing_ok=True)


def script(path, body):
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)
    return path


@pytest.fixture
def programs(tmp_path, monkeypatch):
    """Stand-ins for the three agent programs and the shell, each writing what it was started with."""
    folder = tmp_path / "bin"
    folder.mkdir()
    for name in PROGRAMS.values():
        script(
            folder / name,
            f'if [ "$1" = "--version" ]; then echo "1.2.3 ({name})"; exit 0; fi\n'
            f'{{ echo "args=$*"; echo "tab=$FORMCUT_AGENT_TAB"; echo "config=$FORMCUT_TAB_MCP_CONFIG"; }} > "{tmp_path}/{name}.seen"\n'
            "exec sleep 30\n",
        )
    shell = script(
        tmp_path / "plainsh", f'echo "tab=[$FORMCUT_AGENT_TAB] config=[$FORMCUT_TAB_MCP_CONFIG]" > "{tmp_path}/shell.seen"\nexec sleep 30\n'
    )
    monkeypatch.setenv("PATH", f"{folder}:/usr/bin:/bin")
    monkeypatch.setenv("SHELL", str(shell))
    dock_tabs._found.clear()
    yield tmp_path
    with dock_tabs._lock:
        left = list(dock_tabs._tabs.values())
        dock_tabs._tabs.clear()
    for tab in left:
        tab.close()


def seen(path, seconds=5.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if path.exists() and path.read_text().endswith("\n"):
            return dict(line.split("=", 1) for line in path.read_text().splitlines())
        time.sleep(0.05)
    raise AssertionError(f"{path.name} was never written")


def ask(client, **headers):
    return client.post(
        "/api/agent-access/request", headers={**LOCAL, **headers}, json={"tool": "formcut_edit", "agent": "test", "client": "a client"}
    )


def test_the_new_reads_answer_the_window_only(bare, window):
    for path in ("/api/terminal/tabs", "/api/terminal/agents", "/api/agent-access/waiting", "/api/agent-access/events"):
        assert bare.get(path).status_code == 403, path
        assert window.get(path).status_code == 200, path
    assert window.get("/api/terminal/status").json()["contract"] == terminal.DOCK_CONTRACT


def test_agent_status_in_one_call(window, programs, monkeypatch):
    found = window.get("/api/terminal/agents").json()
    assert found["contract"] == terminal.DOCK_CONTRACT
    for kind, name in PROGRAMS.items():
        assert found[kind]["installed"] is True and found[kind]["version"] == f"1.2.3 ({name})" and found[kind]["install"] == ""
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    missing = window.get("/api/terminal/agents").json()
    for kind in PROGRAMS:
        assert missing[kind] == {
            "installed": False,
            "version": None,
            "install": dock_tabs.PROGRAMS[kind]["install"],
            "signedIn": None,
            "title": dock_tabs.PROGRAMS[kind]["title"],
        }
    refused = window.post("/api/terminal/tabs", json={"kind": "codex"})
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "notInstalled"


def test_a_plain_shell_tab_carries_no_tab_token(window, programs):
    tab = window.post("/api/terminal/tabs", json={"kind": "shell"}).json()
    assert tab["kind"] == "shell" and tab["alive"] is True
    assert seen(programs / "shell.seen") == {"tab": "[] config=[]"}
    assert [t["id"] for t in window.get("/api/terminal/tabs").json()["tabs"]] == [tab["id"]]
    assert window.delete(f"/api/terminal/tabs/{tab['id']}").json() == {"ok": True}
    assert window.delete(f"/api/terminal/tabs/{tab['id']}").json() == {"ok": True}
    assert window.get("/api/terminal/tabs").json()["tabs"] == []


def test_each_agent_tab_has_its_own_token_and_a_closed_tab_s_token_is_refused(bare, window, programs, stored_choice, monkeypatch):
    monkeypatch.setitem(extensions._seen, "poll", 0.0)
    tokens = {}
    for kind, name in PROGRAMS.items():
        tab = window.post("/api/terminal/tabs", json={"kind": kind}).json()
        assert tab["kind"] == kind and tab["alive"] is True
        told = seen(programs / f"{name}.seen")
        token, config = told["tab"], told["config"]
        assert agent_access.tab_live(token)
        assert token not in told["args"]
        assert token not in subprocess.run(["ps", "-eo", "args"], capture_output=True, text=True, check=True).stdout
        assert stat.S_IMODE(os.stat(config).st_mode) == 0o600
        entry = json.loads(Path(config).read_text(encoding="utf-8"))["mcpServers"][dock_tabs.MCP_NAME]
        assert entry["env"] == {agent_access.TAB_ENV: "${" + agent_access.TAB_ENV + "}"}
        assert ask(bare, **{agent_access.TAB_HEADER: token}).status_code == 200
        tokens[kind] = (tab["id"], token, config)
    assert len({token for _, token, _ in tokens.values()}) == 3
    for tab_id, token, config in tokens.values():
        assert window.delete(f"/api/terminal/tabs/{tab_id}").status_code == 200
        assert not agent_access.tab_live(token)
        assert ask(bare, **{agent_access.TAB_HEADER: token}).status_code == 403
        assert not os.path.exists(config)


def test_a_restart_keeps_the_id_and_changes_the_token(window, programs):
    tab = window.post("/api/terminal/tabs", json={"kind": "claude", "prompt": "cut the pauses"}).json()
    first = seen(programs / "claude.seen")
    assert first["args"].endswith("cut the pauses") and "--mcp-config" in first["args"]
    (programs / "claude.seen").unlink()
    again = window.post(f"/api/terminal/tabs/{tab['id']}/restart").json()
    second = seen(programs / "claude.seen")
    assert again["id"] == tab["id"] and again["alive"] is True
    assert second["tab"] != first["tab"] and not agent_access.tab_live(first["tab"]) and agent_access.tab_live(second["tab"])
    assert window.post("/api/terminal/tabs/gone/restart").json()["detail"]["code"] == "gone"


def test_closing_a_tab_ends_a_program_that_ignores_the_hang_up(window, programs, monkeypatch):
    monkeypatch.setenv("SHELL", str(script(programs / "deafsh", f'trap "" HUP\necho "pid=$$" > "{programs}/deaf.seen"\nexec sleep 30\n')))
    tab = window.post("/api/terminal/tabs", json={"kind": "shell"}).json()
    pid = int(seen(programs / "deaf.seen")["pid"])
    assert os.path.exists(f"/proc/{pid}") or subprocess.run(["ps", "-p", str(pid)], capture_output=True, check=False).returncode == 0
    window.delete(f"/api/terminal/tabs/{tab['id']}")
    end = time.monotonic() + 5
    while time.monotonic() < end and subprocess.run(["ps", "-p", str(pid)], capture_output=True, check=False).returncode == 0:
        time.sleep(0.1)
    assert subprocess.run(["ps", "-p", str(pid)], capture_output=True, check=False).returncode != 0


def test_the_tab_socket_replays_and_says_exit_as_its_own_frame(window, programs, monkeypatch):
    monkeypatch.setenv("SHELL", str(script(programs / "shortsh", 'echo "hello from the tab"\nexit 3\n')))
    tab = window.post("/api/terminal/tabs", json={"kind": "shell"}).json()
    end = time.monotonic() + 5
    while time.monotonic() < end and window.get("/api/terminal/tabs").json()["tabs"][0]["alive"]:
        time.sleep(0.05)
    ticket = window.post("/api/window/ticket").json()["ticket"]
    with window.websocket_connect(f"/api/terminal/tabs/{tab['id']}/ws?ticket={ticket}") as ws:
        first, then = ws.receive_json(), ws.receive_json()
    assert first["type"] == "replay" and "hello from the tab" in first["data"] and first["alive"] is False
    assert then == {"type": "exit", "code": 3}
    ticket = window.post("/api/window/ticket").json()["ticket"]
    with window.websocket_connect(f"/api/terminal/tabs/unknown/ws?ticket={ticket}") as ws:
        assert ws.receive_json() == {"type": "gone"}


def test_the_question_carries_what_the_dialog_needs_and_is_withdrawn(bare, window, stored_choice, monkeypatch):
    monkeypatch.setattr(agent_access, "ASK_SECONDS", 1.0)
    start = window.get("/api/agent-access/events").json()["seq"]
    answers = ["once", None]
    asked = []

    def stand_in_window():
        for answer in answers:
            request = None
            while request is None:
                request = window.get("/api/extensions/agent/next?wait=2").json()["request"]
            asked.append(request)
            if answer:
                window.post(f"/api/extensions/agent/{request['id']}", json={"result": answer})

    window.get("/api/extensions/agent/next?wait=0")
    thread = threading.Thread(target=stand_in_window, daemon=True)
    thread.start()
    before = time.time() * 1000
    assert ask(bare).status_code == 200
    refused = ask(bare)
    thread.join(timeout=5)
    assert refused.status_code == 403 and "Nobody answered" in refused.json()["detail"]
    first = asked[0]
    assert first["action"] == "consent" and first["tool"] == "formcut_edit" and first["agent"] == "test" and first["notice"] == ""
    assert first["client"] == "a client" and first["what"] == "run formcut_edit" and first["always"] == "all" and first["escape"] == "deny"
    assert set(first["offers"]) <= {"deny", "once", "always"} and {"deny", "once"} <= set(first["offers"])
    assert before < first["expires"] <= time.time() * 1000 + 1000
    events = window.get(f"/api/agent-access/events?after={start}&wait=0").json()["events"]
    assert [(e["type"], e["id"], e["reason"]) for e in events] == [
        ("withdrawn", asked[0]["id"], "answered"),
        ("withdrawn", asked[1]["id"], "expired"),
    ]
    assert window.get("/api/agent-access/waiting").json()["requests"] == []
