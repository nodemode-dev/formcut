# Automation surface

## JSON-RPC methods

capabilities
- catalogue
- session.hello
- media.list
- media.import
- project.list
- project.create
- project.get
- project.edit
- project.undo
- project.redo
- project.export
- job.result
- job.status
- job.cancel

## Edit operations

`project.edit` takes a command list. Operations include project.settings,
clip.add, clip.update, clip.remove, clip.split, clip.trim, track.add,
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

- `formcut_status`
- `formcut_list_media`
- `formcut_import_media`
- `formcut_create_project`
- `formcut_get_project`
- `formcut_list_projects`
- `formcut_add_clip`
- `formcut_set_frame`
- `formcut_render`
- `formcut_render_status`
- `formcut_cancel_render`
- `formcut_catalogue`
- `formcut_edit`
- `formcut_capabilities`

Built on mcp 2.2.0: the server class is `MCPServer`, imported from
`mcp.server.mcpserver`, and transport is stdio. Its own virtualenv exists
because the SDK pins a newer starlette than the engine's FastAPI accepts.
`FORMCUT_ENGINE` overrides the engine address; `FORMCUT_MCP_SESSION` names the
session the app shows.
