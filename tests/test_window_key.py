"""The window key and outside-agent consent.

Every write needs the per-launch window key unless its path is on the short open
list; sockets need a one-time ticket bought with the key; outside agents get a
pass for one tool call only by the stored choice or the window's answer; only
the window can change that choice, which is sealed with a key in the system
keychain.
"""

import re
import sys
import types

import pytest
from app import agent_access, seal, security, window_key
from app.main import app
from conftest import bare as as_any_program
from conftest import window_headers
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

OWN = "http://127.0.0.1:8123"
LOCAL = {"x-formcut-local": "1"}
OPEN = {
    ("POST", "/api/window/key"),
    ("POST", "/api/agent-access/request"),
    ("DELETE", "/api/agent-access/pass"),
    ("POST", "/api/rpc/read"),
}
REFUSED = {"Only the formcut window can do this", "Local API request refused"}


@pytest.fixture(scope="module")
def bare():
    return as_any_program(TestClient(app, base_url=OWN))


@pytest.fixture(scope="module")
def window():
    return TestClient(app, base_url=OWN, headers=window_headers())


@pytest.fixture
def keychain(monkeypatch):
    """A stand-in system keychain."""
    store: dict = {}
    fake = types.SimpleNamespace(
        get_password=lambda s, a: store.get((s, a)),
        set_password=lambda s, a, v: store.__setitem__((s, a), v),
    )
    monkeypatch.setitem(sys.modules, "keyring", fake)
    seal.reset()
    yield store
    seal.reset()


@pytest.fixture
def no_keychain(monkeypatch):
    monkeypatch.setitem(sys.modules, "keyring", None)
    seal.reset()
    yield
    seal.reset()


@pytest.fixture
def stored_choice():
    agent_access.STORE.unlink(missing_ok=True)
    yield
    agent_access.STORE.unlink(missing_ok=True)


def write_operations():
    return [(m.upper(), path) for path, item in app.openapi()["paths"].items() for m in item if m.upper() not in security.READS]


def test_the_open_list_is_short_and_named():
    assert set(security.OPEN) == {path for _, path in OPEN}


def test_every_write_route_needs_the_window_key(bare):
    ops = write_operations()
    assert len(ops) > 150
    answered = []
    for method, path in ops:
        if (method, path) in OPEN:
            continue
        url = re.sub(r"\{[^}]+\}", "x", path)
        for headers in ({}, LOCAL, {**LOCAL, window_key.HEADER: "x" * 43}, {**LOCAL, agent_access.PASS_HEADER: "x" * 32}):
            r = bare.request(method, url, json={}, headers=headers)
            if r.status_code != 403 or r.text not in REFUSED:
                answered.append(f"{method} {path} {r.status_code}")
    assert not answered, (
        "write routes that answer without the window key (add the key, or name the path in security.OPEN with its caller): "
        + ", ".join(answered)
    )


def test_the_window_writes_with_the_key(window):
    r = window.post("/api/rpc", json={"jsonrpc": "2.0", "id": 1, "method": "project.list"})
    assert r.status_code == 200 and isinstance(r.json()["result"], list)


def test_the_bootstrap_answers_once(bare, monkeypatch):
    monkeypatch.setitem(window_key.STATE, "claimed", False)
    monkeypatch.setitem(window_key.STATE, "secondClaim", False)
    first = bare.post("/api/window/key", headers=LOCAL)
    assert first.status_code == 200 and first.json()["key"] == window_key.KEY
    assert bare.post("/api/window/key", headers=LOCAL).status_code == 409
    assert bare.get("/api/window/state").json()["secondClaim"] is True


def test_packaged_mode_has_no_bootstrap(bare, monkeypatch):
    monkeypatch.setenv(window_key.STDOUT_ENV, "1")
    monkeypatch.setitem(window_key.STATE, "claimed", False)
    assert bare.post("/api/window/key", headers=LOCAL).status_code == 404


def test_a_socket_needs_a_ticket_and_a_ticket_works_once(bare, window):
    with pytest.raises(WebSocketDisconnect), bare.websocket_connect("/api/rpc/ws") as ws:
        ws.receive_json()
    with pytest.raises(WebSocketDisconnect), bare.websocket_connect("/api/rpc/ws?ticket=made-up") as ws:
        ws.receive_json()
    assert bare.post("/api/window/ticket", headers=LOCAL).status_code == 403
    ticket = window.post("/api/window/ticket").json()["ticket"]
    with bare.websocket_connect(f"/api/rpc/ws?ticket={ticket}") as ws:
        ws.send_json({"jsonrpc": "2.0", "id": 7, "method": "project.list"})
        assert ws.receive_json()["id"] == 7
    with pytest.raises(WebSocketDisconnect), bare.websocket_connect(f"/api/rpc/ws?ticket={ticket}") as ws:
        ws.receive_json()


def test_the_terminal_socket_needs_a_ticket(bare):
    with pytest.raises(WebSocketDisconnect), bare.websocket_connect("/api/terminal/ws") as ws:
        ws.receive_text()


def test_the_window_queue_is_read_with_the_key_only(bare, window):
    assert bare.get("/api/extensions/agent/next?wait=0").status_code == 403
    assert window.get("/api/extensions/agent/next?wait=0").status_code == 200


def test_reads_go_without_the_key_and_writes_are_refused_there(bare):
    listed = bare.post("/api/rpc/read", headers=LOCAL, json={"jsonrpc": "2.0", "id": 1, "method": "project.list"})
    assert isinstance(listed.json()["result"], list)
    refused = bare.post(
        "/api/rpc/read", headers=LOCAL, json={"jsonrpc": "2.0", "id": 1, "method": "project.create", "params": {"title": "no"}}
    )
    assert refused.json()["error"]["code"] == -32601


def ask(client, tool="formcut_edit", **headers):
    return client.post("/api/agent-access/request", headers={**LOCAL, **headers}, json={"tool": tool, "agent": "test"})


def test_ask_with_no_window_refuses_at_once(bare, stored_choice, monkeypatch):
    from app import extensions

    monkeypatch.setitem(extensions._seen, "poll", 0.0)
    r = ask(bare)
    assert r.status_code == 403 and "no formcut window is open" in r.json()["detail"]


@pytest.mark.parametrize(("answer", "granted", "kept"), [("deny", False, "ask"), ("once", True, "ask"), ("always", True, "allowed")])
def test_the_window_answers(bare, stored_choice, keychain, monkeypatch, answer, granted, kept):
    from app import extensions

    seen = {}

    def window_answer(action, payload, seconds):
        seen.update(action=action, seconds=seconds, **payload)
        return {"result": answer}

    monkeypatch.setattr(extensions, "ask_window", window_answer)
    r = ask(bare)
    assert (r.status_code == 200) is granted
    assert seen["action"] == "consent" and seen["tool"] == "formcut_edit" and seen["seconds"] == 120
    assert agent_access.state()["choice"] == kept


def test_a_pass_writes_but_never_reaches_the_window_routes(bare, window, stored_choice, keychain):
    assert window.put("/api/agent-access", json={"choice": "allowed"}).json()["seal"] == "ok"
    given = ask(bare).json()["pass"]
    with_pass = {**LOCAL, agent_access.PASS_HEADER: given}
    assert bare.post("/api/rpc", headers=with_pass, json={"jsonrpc": "2.0", "id": 1, "method": "project.list"}).status_code == 200
    assert bare.put("/api/agent-access", headers=with_pass, json={"choice": "allowed"}).status_code == 403
    assert bare.post("/api/window/ticket", headers=with_pass).status_code == 403
    assert bare.post("/api/extensions/agent/x", headers=with_pass, json={}).status_code == 403
    bare.delete("/api/agent-access/pass", headers=with_pass)
    assert bare.post("/api/rpc", headers=with_pass, json={"jsonrpc": "2.0", "id": 1, "method": "project.list"}).status_code == 403


def test_blocked_refuses_and_only_the_window_changes_the_choice(bare, window, stored_choice, keychain):
    assert bare.put("/api/agent-access", headers=LOCAL, json={"choice": "allowed"}).status_code == 403
    assert window.put("/api/agent-access", json={"choice": "blocked"}).status_code == 200
    r = ask(bare)
    assert r.status_code == 403 and "blocked" in r.json()["detail"]


def test_a_live_agent_terminal_tab_is_not_asked(bare, stored_choice, keychain, window):
    tab = agent_access.open_tab()
    assert ask(bare, **{agent_access.TAB_HEADER: tab}).status_code == 200
    agent_access.close_tab(tab)
    assert ask(bare, **{agent_access.TAB_HEADER: tab}).status_code == 403


def test_blocked_refuses_a_live_agent_terminal_tab_too(bare, stored_choice, keychain, window):
    window.put("/api/agent-access", json={"choice": "blocked"})
    tab = agent_access.open_tab()
    r = ask(bare, **{agent_access.TAB_HEADER: tab})
    agent_access.close_tab(tab)
    assert r.status_code == 403 and "blocked" in r.json()["detail"]


def test_a_hand_edit_reads_as_ask_and_says_so(bare, window, stored_choice, keychain):
    window.put("/api/agent-access", json={"choice": "allowed"})
    agent_access.STORE.write_text('{"outsideAgents": "allowed", "seal": "0000"}', encoding="utf-8")
    state = window.get("/api/agent-access").json()
    assert state["choice"] == "ask" and state["sealBroken"] is True and state["notice"]


def test_no_keychain_starts_and_never_honours_allowed(window, stored_choice, no_keychain):
    assert window.get("/api/agent-access").json()["seal"] == "unavailable"
    assert window.put("/api/agent-access", json={"choice": "allowed"}).status_code == 409
    agent_access.STORE.write_text('{"outsideAgents": "allowed"}', encoding="utf-8")
    assert window.get("/api/agent-access").json()["choice"] == "ask"


def test_the_mcp_server_asks_before_every_tool_that_is_not_read_only(monkeypatch):
    from app import agent_mcp

    asked = []
    monkeypatch.setattr(agent_mcp, "_ask", lambda tool: (asked.append(tool), (False, "refused"))[1])
    assert agent_mcp.formcut_create_project(title="x") == "refused"
    assert asked == ["formcut_create_project"]
    assert agent_mcp.formcut_create_project(title="x", fps=24.5) == agent_mcp.RATE_REFUSED
    assert asked == ["formcut_create_project"]
