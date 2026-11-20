"""How to connect an AI agent to this formcut, for Settings, Connections.

Every MCP client launches a local server the same way, a command and its
arguments, and formcut's is itself: the installed app's engine run as
`formcut-engine --mcp` (agent_mcp.py), or, from a repository, its Python with
mcp/formcut_mcp.py. This answers with that command for this copy of formcut and
the exact text each client wants, paths quoted for this system, so connecting
is one paste. The server finds the running app by itself (discovery.py).
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import agent_lookup

router = APIRouter(prefix="/api/agents", tags=["agents"])
ROOT = Path(__file__).resolve().parents[2]


def server_command() -> tuple[str, list[str]]:
    """The command an MCP client runs to start formcut's server, and its arguments."""
    if getattr(sys, "frozen", False):
        return sys.executable, ["--mcp"]
    return sys.executable, [str(ROOT / "mcp" / "formcut_mcp.py")]


def _shell_line(words: list[str]) -> str:
    return subprocess.list2cmdline(words) if sys.platform == "win32" else " ".join(shlex.quote(word) for word in words)


def _claude_desktop_config() -> str:
    if sys.platform == "darwin":
        return "~/Library/Application Support/Claude/claude_desktop_config.json"
    if sys.platform == "win32":
        return r"%APPDATA%\Claude\claude_desktop_config.json"
    return "~/.config/Claude/claude_desktop_config.json"


def clients() -> list[dict]:
    command, args = server_command()
    stdio = {"command": command, "args": args}
    return [
        {
            "id": "claude-code",
            "name": "Claude Code",
            "kind": "command",
            "file": None,
            "text": _shell_line(["claude", "mcp", "add", "formcut", "--scope", "user", "--", command, *args]),
        },
        {
            "id": "codex",
            "name": "Codex",
            "kind": "file",
            "file": "~/.codex/config.toml",
            # TOML basic strings take JSON's escapes, so json.dumps quotes Windows paths correctly.
            "text": f"[mcp_servers.formcut]\ncommand = {json.dumps(command)}\nargs = {json.dumps(args)}\n",
        },
        {
            "id": "cursor",
            "name": "Cursor",
            "kind": "file",
            "file": "~/.cursor/mcp.json",
            "text": json.dumps({"mcpServers": {"formcut": stdio}}, indent=2),
        },
        {
            "id": "antigravity",
            "name": "Antigravity",
            "kind": "file",
            "file": "~/.gemini/config/mcp_config.json",
            "text": json.dumps({"mcpServers": {"formcut": stdio}}, indent=2),
        },
        {
            "id": "claude-desktop",
            "name": "Claude Desktop",
            "kind": "file",
            "file": _claude_desktop_config(),
            "text": json.dumps({"mcpServers": {"formcut": stdio}}, indent=2),
        },
        {
            "id": "vscode",
            "name": "VS Code",
            "kind": "file",
            "file": ".vscode/mcp.json",
            "text": json.dumps({"servers": {"formcut": {"type": "stdio", **stdio}}}, indent=2),
        },
        {"id": "any", "name": "", "kind": "command", "file": None, "text": _shell_line([command, *args])},
    ]


@router.get("/connect")
def connect() -> dict:
    command, args = server_command()
    return {"command": command, "args": args, "installed": bool(getattr(sys, "frozen", False)), "clients": clients(), "sep": os.sep}


class InstallBody(BaseModel):
    client: str


def _run(words: list[str]) -> subprocess.CompletedProcess:
    from . import dock_tabs

    return agent_lookup.run(words, dock_tabs.agent_env(words[0]), 60)


def _antigravity(command: str, args: list[str]) -> dict:
    """Writes formcut into Antigravity's MCP servers file, keeping every other server and key that is there."""
    path = Path.home() / ".gemini" / "config" / "mcp_config.json"
    older = Path.home() / ".gemini" / "antigravity-cli" / "mcp_config.json"
    seen = str(older) if older.is_file() and not path.is_file() else None
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}") if path.is_file() else {}
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        raise HTTPException(409, f"{path} is not an MCP servers file formcut can read, so it was left alone")
    entry = {"command": command, "args": args}
    have = data.get("mcpServers", {}).get("formcut")
    ours = isinstance(have, dict) and Path(str(have.get("command", ""))).name == Path(command).name
    if have is not None and have != entry and not ours:
        raise HTTPException(409, f"{path} has a server named formcut that formcut did not write, so it was left alone")
    if have != entry:
        data.setdefault("mcpServers", {})["formcut"] = entry
        path.parent.mkdir(parents=True, exist_ok=True)
        part = path.with_name(path.name + f".part-{os.getpid()}")
        part.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(part, path)
    return {
        "client": "antigravity",
        "written": str(path),
        "present": have == entry,
        "older": seen,
    }


def _claude_runs(claude: str, command: str, args: list[str]) -> bool:
    """Whether Claude Code's saved formcut entry starts this copy's command with these arguments."""
    fields = {}
    for line in _run([claude, "mcp", "get", "formcut"]).stdout.splitlines():
        key, sep, value = line.strip().partition(":")
        if sep:
            fields[key] = value.strip()
    return fields.get("Command") == command and fields.get("Args", "") == " ".join(args)


@router.post("/install")
def install(body: InstallBody) -> dict:
    """Register formcut's MCP server with a client in one click, so the embedded terminal's agent finds it."""
    command, args = server_command()
    if body.client == "claude-code":
        from . import dock_tabs

        found = dock_tabs.usable("claude")
        if found.state != "runs":
            raise HTTPException(409, dock_tabs.said("claude", found))
        claude = found.path
        add = [claude, "mcp", "add", "formcut", "--scope", "user", "--", command, *args]
        run = _run(add)
        text = (run.stdout + run.stderr).strip()
        present = "already exists" in text
        if present and not _claude_runs(claude, command, args):
            _run([claude, "mcp", "remove", "formcut", "--scope", "user"])
            run = _run(add)
            text = (run.stdout + run.stderr).strip()
            present = False
        if run.returncode and not present:
            raise HTTPException(502, f"claude mcp add failed: {text[-400:]}")
        return {
            "client": "claude-code",
            "written": "claude mcp add formcut --scope user",
            "present": present,
            "detail": text[-400:],
        }
    if body.client == "codex":
        path = Path.home() / ".codex" / "config.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        block = "[mcp_servers.formcut]\ncommand = " + json.dumps(command) + "\nargs = " + json.dumps(args) + "\n"
        if "[mcp_servers.formcut]" in existing:
            head, _, rest = existing.partition("[mcp_servers.formcut]")
            tail = rest.split("\n[", 1)
            rebuilt = head + block + ("\n[" + tail[1] if len(tail) > 1 else "")
        else:
            rebuilt = existing + ("\n" if existing and not existing.endswith("\n") else "") + ("\n" if existing else "") + block
        if existing:
            path.with_suffix(".toml.bak").write_text(existing, encoding="utf-8")
        path.write_text(rebuilt, encoding="utf-8")
        return {
            "client": "codex",
            "written": str(path),
            "present": "[mcp_servers.formcut]" in existing,
            "backup": str(path.with_suffix(".toml.bak")) if existing else None,
        }
    if body.client == "antigravity":
        return _antigravity(command, args)
    raise HTTPException(400, "client must be claude-code, codex or antigravity")
