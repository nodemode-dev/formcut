# Automation surface

## JSON-RPC methods

`capabilities` returns the authoritative list (`backend/app/automation.py`); this is
how it groups. Methods that change nothing answer at `POST /api/rpc/read` for any
local program (`backend/app/read_methods.py`):

- capabilities, catalogue, devices.list, extensions.list
- media.list, media.scenes, media.music, media.qc, media.cutdowns
- project.get, project.list
- job.result
- speech.range, timeline.cuts

Every other method is a write at `POST /api/rpc`: it needs the window key and, for an
outside agent, the person's Allow in the window first.

- session.hello
- media.import, media.proxy, media.beats, media.transcribe, media.ducking
- captions.import (SRT or WebVTT text in, cues out), captions.export (a project's track out as SRT or WebVTT)
- project.create, project.edit, project.undo, project.redo, project.export, project.export_audio
- job.status, job.cancel
- timeline.frames
- extensions.command

## Edit operations

`project.edit` takes a command list. Operations include project.settings,
clip.add, clip.update, clip.remove, clip.split, clip.trim, track.add,
marker.add, marker.update, marker.remove (notes at times on the active timeline),
clips.move, clips.remove, clips.duplicate, clips.add, clips.mute (multi-clip,
the interface's semantics: one call is one undo step, a group move is refused
whole over a locked track) and
track.remove; `capabilities` reports the authoritative list, and an unknown
operation is refused by name.

## Concurrency and results

Edits carry the revision last seen and a stale one is refused with the current
revision named. `project.export` answers `{"job_id": ...}`; `job.status`,
`job.cancel` and `job.result` accept that id under either `id` or `job_id`.
`job.result` returns ready, the output path, name, media type and a URL.

## Events

`GET /api/orchestration/events`, server-sent, with a short backlog and a
fifteen second keepalive comment. Event kinds: `session.open`, `session.close`,
`operation` (session, method), and `job` (job, job_kind, status, progress,
file or error). The job's own kind travels as `job_kind`, because `kind` names
the event type.

## MCP tools

The server declares 34 tools. Their exact names, parameters, limits and effects are in the
formcut-mcp pack, `.claude/skills/formcut-mcp/sub-skills/mcp-workflows/references/tools.md`,
generated from the server by `setup/mcp_tool_reference.py`; this map does not keep its own copy.

Built on mcp 2.2.0: the server class is `MCPServer`, imported from
`mcp.server.mcpserver`, and transport is stdio. It is part of the engine
(app/agent_mcp.py), so the installed app runs it as `formcut-engine --mcp`; it
finds the running engine through engine.json (app/discovery.py).
`FORMCUT_ENGINE` overrides the engine address; `FORMCUT_MCP_SESSION` names the
session the app shows.
