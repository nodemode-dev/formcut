# Automation

Use the running desktop engine's loopback URL, or the development engine at `http://127.0.0.1:8040`. The desktop port is assigned by the OS and appears in the engine startup log. POST JSON-RPC 2.0 to `/api/rpc` with `Content-Type: application/json` and `x-formcut-local: 1`.

```json
{"jsonrpc":"2.0","id":1,"method":"capabilities"}
```

`capabilities` lists current methods, editable properties and command names. `catalogue` lists effect IDs. `project.list`, `project.create`, `project.get`, `project.edit`, `project.undo`, `project.redo` and `project.export` operate on persisted documents. `job.status` and `job.cancel` operate on jobs in the same engine process. `captions.export` writes a project track's captions as SRT or WebVTT text; `captions.import` turns SRT or WebVTT text into cues (start, end, text) for `clip.add`.

```json
{"jsonrpc":"2.0","id":2,"method":"project.create","params":{"title":"Example"}}
```

Use the returned project id and revision for subsequent changes:

```json
{"jsonrpc":"2.0","id":3,"method":"project.edit","params":{"id":"PROJECT_ID","revision":1,"commands":[{"op":"track.add","name":"Titles"}]}}
```

A command can add/update/remove/move/split clips, add/remove tracks, add timelines or update project settings. `clip.update` accepts ordinary document properties. Multi-clip commands act on a set in one call with the interface's semantics: `clips.move` (clipIds, deltaStart, optional deltaTrack; refused whole when any member would land on a locked track or before zero), `clips.remove`, `clips.duplicate` (copies land after their sources), `clips.add` (entries of track and clip) and `clips.mute`; capabilities lists them. A batch of commands is committed as one undo step. Supply the current revision to detect conflicts. REST PUT `/api/projects/{id}` also checks revision. Undo history is retained for the engine session only.

## Orchestration

An external system can identify itself with `session.hello` and pass the
returned session id as `session` in later calls; every call is recorded against
that session and shown in the app under Settings, Connections, so the person in
front of the editor can see who is driving. `media.list` and `media.import`
move assets in (import copies the file rather than consuming it), and
`job.result` returns the finished render's path, name, media type and a URL to
fetch it.

`GET /api/orchestration/events` is a server-sent event stream carrying session
opens and closes, each orchestrated call, and job state with progress every five
percent through to done, cancelled or failed. It keeps a short backlog, so a
subscriber that connects mid-render still sees the job it cares about, and sends
a keepalive comment every fifteen seconds. Jobs can be cancelled from either
side: `job.cancel` over RPC, or the cancel control in the Connections tab.

Rendering: POST `/api/render/export` with `{ "project": DOCUMENT, "format": "mp4", "quality": "high" }`. The response contains `job_id`, not `id`. Over JSON-RPC, `project.export` returns the same `job_id`, and `job.status` and `job.cancel` accept it as either `id` or `job_id`. Poll GET `/api/jobs/{job_id}`, cancel with DELETE, and download GET `/api/jobs/{job_id}/file` after status `done`. WebM is also supported; qualities are high, medium and low. The old `/api/export` route remains a compatibility renderer; use `/api/render/export` for current features.

The backend CLI accepts one JSON-RPC request per line on stdin and emits responses on stdout. From `backend/`:

```sh
python -m app.cli
python -m app.cli --tcp 18051
python -m app.cli --unix /tmp/formcut.sock
python -m app.cli --grpc 18052
```

TCP binds to 127.0.0.1 and uses newline-delimited JSON. Unix sockets require OS support; remove a stale socket path after an interrupted server. The generic gRPC method is `/formcut.Automation/Call`, unary request/response with UTF-8 JSON bytes. It is not a generated protobuf service, and no compatibility with any other product's protocol is claimed. The frozen entry point accepts `--headless` before these CLI options.

WebSocket `/api/rpc/ws` sends the same JSON objects over a loopback connection. HTTP, stdin, TCP and gRPC have been exercised, most recently a full HTTP sweep that created a project, applied a four-command edit, rejected a stale revision, ran undo and redo, answered a batch, and drove an export to a finished file. WebSocket and Unix socket are implemented but still unverified. Do not use the GUI and a second standalone CLI process as concurrent writers to one data directory. Use HTTP RPC on the GUI's engine instead.


### v0.56.0
`project.edit` adds `clips.split`, `clip.rejoin`, `clip.freeze-insert`, `clip.reattach`; magnetic tracks settle after each batch; `clip_properties` includes `reversed`; per-timeline formats apply to `project.export`.


### v0.57.0
Title styles ride `clip.text` patches like any other style field, so the full property set is scriptable; `/api/presets/titles` lists the built-ins.
