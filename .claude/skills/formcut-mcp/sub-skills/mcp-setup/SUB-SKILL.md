---
name: mcp-setup
description: "Connect formcut's MCP server to Claude Code, Codex, Cursor, Claude Desktop, VS Code or another MCP client, and diagnose a connection that fails. Use for adding the server to a client, the server not appearing, formcut not answering, and environment variables."
---

# MCP Setup

## Purpose

Get the 21 formcut tools reachable from an MCP client and driving the formcut that is running, and diagnose it when they are not.

## Where the server comes from

The installed app includes it: its engine, run as `formcut-engine --mcp`, is the MCP server, over stdio. Nothing else is installed. From a checkout, `mcp/formcut_mcp.py` runs the same server (`backend/app/agent_mcp.py`) with the engine's virtualenv, or with one of its own from `cd mcp && ./oc_install`.

## Add it to a client

The simplest route is in the app: **Settings, Connections, AI agents** shows, for each client, the exact command or config with this copy of formcut's path filled in, and a Copy button. The shapes, with `[engine]` for the path it shows (on macOS inside `formcut.app/Contents/MacOS/formcut-engine`):

- **Claude Code:** `claude mcp add formcut --scope user -- [engine] --mcp`, then `claude mcp list` shows whether it connects.
- **Codex:** in `~/.codex/config.toml`, a `[mcp_servers.formcut]` table with `command = "[engine]"` and `args = ["--mcp"]`.
- **Cursor:** in `~/.cursor/mcp.json`, `mcpServers.formcut` with `command` and `args`.
- **Claude Desktop:** the same `mcpServers` entry in `claude_desktop_config.json` (on macOS in `~/Library/Application Support/Claude/`, on Windows in `%APPDATA%\Claude\`), then restart it.
- **VS Code:** in `.vscode/mcp.json`, `servers.formcut` with `"type": "stdio"`, `command` and `args`.
- **Any other client:** the command and `--mcp`; the transport is stdio.

## How it finds formcut

While formcut runs, its engine publishes its address in `engine.json` in formcut's data folder, and withdraws it when it stops. Every call reads it afresh and checks that formcut answers there, so quitting and reopening formcut breaks no connection, and a file left by an engine that was killed is ignored.

| Variable | Default | What it does |
| --- | --- | --- |
| `FORMCUT_ENGINE` | none | An engine address to use instead of finding the running app. Without it: the published address, else `http://127.0.0.1:8040`, where `./formcut` starts a source run. |
| `FORMCUT_DATA_DIR` | formcut's data folder | Where to look for `engine.json`; set it when the app runs with a custom data folder. |
| `FORMCUT_MCP_SESSION` | `mcp` | The name the server gives itself to the engine; formcut shows it under Settings, Connections. |
| `FORMCUT_MCP_TIMEOUT` | `120` | Seconds before a call to the engine gives up. |

## When it does not work

Work through `checklists/connection-troubleshooting.md` in order. Most failures are one of the first two steps, and neither is a problem with this skill or with the tools.

## Gate

The client lists the server as connected, and `formcut_status` returns the engine's version and address rather than an error.
