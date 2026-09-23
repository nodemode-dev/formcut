---
name: orchestration-and-mcp
description: >-
  The JSON-RPC automation surface, orchestration sessions and the event stream, and the stdio MCP server over the engine.
---

# orchestration and MCP

How anything outside the interface drives formcut. Load `references/automation-surface.md` for the method list, event shapes and the MCP tool inventory.

## The automation surface

`POST /api/rpc` is JSON-RPC 2.0, also reachable over websocket, stdin, TCP and gRPC-shaped framing from `cli.py`. Fifteen methods: capabilities, catalogue, session.hello, media.list, media.import, project.list, project.create, project.get, project.edit, project.undo, project.redo, project.export, job.result, job.status, job.cancel. Batch requests answer only the messages carrying an id.

Edits carry optimistic concurrency: `project.edit` takes the revision the caller last saw and refuses a stale one by naming the current revision. `project.export` answers with `job_id`, and the job methods accept that id under either `id` or `job_id`, because a client following the reply it was just given should not have to translate.

## Orchestration

An orchestrator calls `session.hello`, then passes its session id as `session` on later calls. Every call is recorded against the session and announced. `GET /api/orchestration/events` is plain server-sent events with a short backlog and a fifteen second keepalive, carrying session opens and closes, each operation, and job state with progress. Cancellation belongs to both sides: `job.cancel` over RPC, or the cancel control in the app's Connections tab.

ANA connecting in is the intended direction and is deferred: the surface above is what it will use, so extend it rather than adding a second path.

## The MCP server

For connecting the server, driving formcut through it, or changing its tools, load the formcut-mcp pack at `.claude/skills/formcut-mcp/`: it carries the workflows, the recovery steps and a tool reference generated from the server. This section is the architectural summary.

`backend/app/agent_mcp.py` is a stdio MCP server built on mcp 2.2 (`MCPServer`), answering the 2025-11-25 protocol and the stateless 2026-07-28 revision. It is part of the engine, so the installed app runs it as `formcut-engine --mcp`. Twenty-one tools, workflow shaped rather than endpoint shaped, returning explicit handles and putting failures in the result text with the recovery action.

Settings, Connections, AI agents gives each client the exact command or config (`app/agent_connect.py`). The server finds the running engine through `engine.json` (`app/discovery.py`); `FORMCUT_ENGINE` overrides it. It identifies itself to the engine with `session.hello`, so a person watching the app sees the agent driving.

When adding a tool: name it `formcut_verb_noun`, write the description for a model choosing between tools, take and return handles rather than holding state, and say in the failure text what the caller should do next.
