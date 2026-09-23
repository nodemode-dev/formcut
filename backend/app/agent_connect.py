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

from fastapi import APIRouter

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
