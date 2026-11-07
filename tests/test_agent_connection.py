"""An AI agent drives the formcut that is running, installed or from source.

The desktop engine publishes its address (discovery.py); the MCP server, run as
`formcut-engine --mcp` or mcp/formcut_mcp.py, finds it on every call; Settings,
Connections hands each client the exact text to add. The last test does it for
real: the engine started as the app starts it, and the official MCP client
connected to the server.
"""

import asyncio
import json
import os
import re
import shlex
import subprocess
import sys
import tomllib

import pytest
from app import agent_connect, discovery
from conftest import ROOT

ENTRY = ROOT / "backend" / "desktop_entry.py"


@pytest.fixture
def record(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "DATA_DIR", tmp_path)
    monkeypatch.setattr(discovery, "RECORD", tmp_path / "engine.json")
    return tmp_path / "engine.json"


def test_the_engine_record_is_written_and_withdrawn_by_its_owner_only(record):
    discovery.publish("http://127.0.0.1:1234", "9.9.9")
    written = json.loads(record.read_text())
    assert written["url"] == "http://127.0.0.1:1234" and written["pid"] == os.getpid() and written["version"] == "9.9.9"
    record.write_text(json.dumps({**written, "pid": written["pid"] + 1}))
    discovery.withdraw()
    assert record.exists(), "a newer engine's record is not this process's to remove"
    record.write_text(json.dumps(written))
    discovery.withdraw()
    assert not record.exists()


def test_a_stale_or_foreign_record_is_ignored(record):
    assert discovery.running_engine() is None, "no record"
    record.write_text(json.dumps({"url": "http://127.0.0.1:9", "pid": 1}))
    assert discovery.running_engine(timeout=0.5) is None, "nothing answers there"
    record.write_text(json.dumps({"url": "http://example.com:80", "pid": 1}))
    assert discovery.running_engine(timeout=0.5) is None, "only this machine"
    record.write_text("not json")
    assert discovery.running_engine() is None


def test_every_client_gets_text_it_can_read(monkeypatch):
    command, args = "/Applications/My Apps/formcut.app/Contents/MacOS/formcut-engine", ["--mcp"]
    monkeypatch.setattr(agent_connect, "server_command", lambda: (command, args))
    monkeypatch.setattr(agent_connect.sys, "platform", "darwin")
    listed = {client["id"]: client for client in agent_connect.clients()}
    assert set(listed) == {"claude-code", "codex", "cursor", "claude-desktop", "vscode", "any"}
    assert shlex.split(listed["claude-code"]["text"]) == ["claude", "mcp", "add", "formcut", "--scope", "user", "--", command, *args]
    assert tomllib.loads(listed["codex"]["text"])["mcp_servers"]["formcut"] == {"command": command, "args": args}
    for client in ("cursor", "claude-desktop"):
        assert json.loads(listed[client]["text"])["mcpServers"]["formcut"] == {"command": command, "args": args}
    assert json.loads(listed["vscode"]["text"])["servers"]["formcut"] == {"type": "stdio", "command": command, "args": args}
    assert shlex.split(listed["any"]["text"]) == [command, *args]


def test_the_installed_app_runs_its_own_server():
    assert '"--mcp" in sys.argv' in ENTRY.read_text(encoding="utf-8")
    assert '"mcp", "mcp-types"' in (ROOT / "backend" / "freeze.py").read_text(encoding="utf-8"), (
        "the frozen engine carries the SDK's metadata"
    )


def _drive(command, env):
    from mcp.client.stdio import stdio_client

    from mcp import ClientSession, StdioServerParameters

    async def run():
        params = StdioServerParameters(command=command[0], args=command[1:], env=env, cwd=str(ROOT / "backend"))
        async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            status = await session.call_tool("formcut_status", {})
            return len(tools.tools), " ".join(item.text for item in status.content if item.type == "text")

    return asyncio.run(run())


def test_an_agent_drives_the_running_engine(tmp_path):
    pytest.importorskip("mcp")
    env = {**os.environ, "FORMCUT_DATA_DIR": str(tmp_path)}
    env.pop("FORMCUT_ENGINE", None)
    engine = subprocess.Popen(
        [sys.executable, "-u", str(ENTRY)], cwd=ROOT / "backend", env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    try:
        address = None
        for _ in range(400):
            match = re.search(r"Uvicorn running on (http://127\.0\.0\.1:\d+)", engine.stdout.readline() or "")
            if match:
                address = match.group(1)
                break
        assert address, "the engine prints the address the app reads"
        assert json.loads((tmp_path / "engine.json").read_text())["url"] == address
        for command in ([sys.executable, str(ENTRY), "--mcp"], [sys.executable, str(ROOT / "mcp" / "formcut_mcp.py")]):
            count, status = _drive(command, env)
            assert count == 34 and address in status, (command, status[:200])
    finally:
        engine.terminate()
        engine.wait(timeout=30)
    if sys.platform != "win32":
        assert not (tmp_path / "engine.json").exists(), "a stopped engine withdraws its address"
