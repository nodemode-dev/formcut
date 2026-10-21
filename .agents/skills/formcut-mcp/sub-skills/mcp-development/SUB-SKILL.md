---
name: mcp-development
description: "Change formcut's MCP server safely: add, rename, remove or change a tool in mcp/formcut_mcp.py, follow the server's design rules, and keep the README, the site, this pack's tool reference and the tests in step with it."
---

# MCP Development

## Purpose

Change the server without breaking the agents that depend on it. A tool's name, parameters and reply text are a contract: agents learned them from the listing and from this pack, and a silent change breaks them at call time.

## Where things are

| File | What it holds |
| --- | --- |
| `backend/app/agent_mcp.py` | The whole server: the `MCPServer` instance and its instructions, the engine helpers, and every tool. Part of the engine, so the frozen app carries it (`formcut-engine --mcp`, in `backend/desktop_entry.py`). |
| `backend/app/discovery.py` | The engine's published address (`engine.json`) and how the server finds a running engine. |
| `backend/app/agent_connect.py` | `GET /api/agents/connect`: the text each client needs, shown in Settings, Connections. |
| `backend/requirements.txt` | The MCP SDK (`mcp==2.2.*`) is an engine dependency; installing from this file keeps starlette where FastAPI needs it. |
| `mcp/formcut_mcp.py`, `mcp/oc_install` | Run the server from a checkout, with the engine's virtualenv or a separate `mcp/.venv`. |
| `setup/mcp_tool_reference.py` | Writes this pack's tool reference from the server's source; `--check` reports whether it is current. |
| `tests/test_mcp_tools_documented.py` | Checks the README lists every tool, tool descriptions name only real tools, and this pack's tool reference matches the server. |

The server is built on the official Python SDK at 2.2, where the server class is `MCPServer` (named FastMCP in earlier releases). The transport is stdio.

## The design rules, and why

These come from the module's own header, and each exists because breaking it broke agents.

- **Workflow tools, not endpoint coverage.** The engine has about eighty routes; an agent needs a dozen verbs. A new tool is a task someone would ask for ("add a clip"), not a wrapper around one route. Coverage beyond the named tools goes through `formcut_edit`, which takes the engine's own edit operations.
- **Explicit handles, no state.** Return every id and revision the next call needs, as text. Keep nothing between calls, so a dropped connection loses nothing and two agents cannot corrupt each other's view.
- **Surface optimistic concurrency.** Anything that edits a project takes `revision` and returns the new one; a stale revision returns the current one with the instruction to re-read.
- **Errors are results.** Route every engine call through `_rest` or `_rpc`, and turn failures into text naming the recovery action (`_explain` does this for transport errors). Never let an exception reach the host.

## Writing a tool

Declare it with `@mcp.tool(name=..., description=..., annotations=...)`:

- `name` starts with `formcut_`, is a verb phrase, and never changes once shipped. Renaming is removing one tool and adding another.
- `description` says what it does, what it returns, and which tool uses that next. Name only tools that exist: a description that points at a missing tool sends every agent to a call that fails.
- `annotations` state `readOnlyHint`, and `destructiveHint` for anything that discards work, with `openWorldHint` false; hosts use them to decide what needs confirmation.
- Each parameter is `Annotated[type, Field(description=..., ge=..., le=...)]`, so limits are enforced before the engine is called and the host shows what each value means.

## After any change

Work through `checklists/tool-change.md`. It exists because the README once listed 14 tools while the server had 16, and a description pointed agents at a tool that was never written.

## Gate

`checklists/tool-change.md` is complete, the test suite passes, and the changed tool has been called from a host against a running engine.
