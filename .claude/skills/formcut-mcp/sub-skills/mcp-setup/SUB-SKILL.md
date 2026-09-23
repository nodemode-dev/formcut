---
name: mcp-setup
description: "Install formcut's MCP server, register it with an MCP host, point it at the engine, and diagnose a connection that fails. Use for the server not appearing, the engine not answering, host configuration, and environment variables."
---

# MCP Setup

## Purpose

Get the 16 formcut tools reachable from an MCP host and pointed at a running engine, and diagnose it when they are not.

## Install

The server runs in its own virtual environment, because the MCP SDK needs a newer starlette than the engine's FastAPI accepts. From a formcut checkout:

```bash
cd mcp && ./oc_install
```

It creates `mcp/.venv`, installs `mcp/requirements.txt` (the MCP SDK from 2.2 up to 3, and httpx), and prints the two values a host needs: the command, `mcp/.venv/bin/python` as an absolute path, and the argument, the absolute path of `mcp/formcut_mcp.py`.

## Register with a host

Claude Code, from any folder:

```bash
claude mcp add formcut -- [absolute path]/mcp/.venv/bin/python [absolute path]/mcp/formcut_mcp.py
```

Add `-e FORMCUT_ENGINE=http://127.0.0.1:8040` before the `--` to set the engine address explicitly. `claude mcp list` then shows whether it connects.

Claude Desktop reads `claude_desktop_config.json` (on macOS in `~/Library/Application Support/Claude/`, on Windows in `%APPDATA%\Claude\`). Add the server under `mcpServers`, then restart the app:

```json
{
  "mcpServers": {
    "formcut": {
      "command": "[absolute path]/mcp/.venv/bin/python",
      "args": ["[absolute path]/mcp/formcut_mcp.py"],
      "env": { "FORMCUT_ENGINE": "http://127.0.0.1:8040" }
    }
  }
}
```

Any other host takes the same command and argument; the transport is stdio.

## Point it at the engine

| Variable | Default | What it does |
| --- | --- | --- |
| `FORMCUT_ENGINE` | `http://127.0.0.1:8040` | The engine the tools call. `./formcut` starts the engine there from a source checkout. |
| `FORMCUT_MCP_SESSION` | `mcp` | The name the server gives itself to the engine; formcut shows it under Settings, Connections. |
| `FORMCUT_MCP_TIMEOUT` | `120` | Seconds before a call to the engine gives up. |

The desktop app starts its engine on a random port and does not publish it, so the server cannot find it. Drive formcut from a source run (`./formcut`), or set `FORMCUT_ENGINE` to an engine whose address is known.

## When it does not work

Work through `checklists/connection-troubleshooting.md` in order. Most failures are one of the first two steps, and neither is a problem with this skill or with the tools.

## Gate

The host lists the server as connected, and `formcut_status` returns the engine's version rather than an error.
