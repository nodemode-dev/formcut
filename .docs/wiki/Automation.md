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

A command can add/update/remove/move/split clips, add/remove tracks, add timelines, update project settings, or add, update and remove markers on the active timeline (`marker.add` with `t`, `colour`, `note`; `marker.update`; `marker.remove`). `clip.update` accepts ordinary document properties. Multi-clip commands act on a set in one call with the interface's semantics: `clips.move` (clipIds, deltaStart, optional deltaTrack; refused whole when any member would land on a locked track or before zero), `clips.remove`, `clips.duplicate` (copies land after their sources), `clips.add` (entries of track and clip) and `clips.mute`; capabilities lists them. A batch of commands is committed as one undo step. Supply the current revision to detect conflicts. REST PUT `/api/projects/{id}` also checks revision. Undo history is retained for the engine session only.

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
`project.edit` adds `clips.split`, `clip.rejoin`, `clip.freeze-insert`, `clip.reattach`; magnetic tracks settle after each batch; `clip_properties` includes `reversed` and `audioStream` (which of the media's audio streams a clip plays); per-timeline formats apply to `project.export`.


### v0.57.0
Title styles ride `clip.text` patches like any other style field, so the full property set is scriptable; `/api/presets/titles` lists the built-ins.


### v1.56.0 to v1.60.0 (the repository's own numbering, which diverged from the plan's)
`project.export` and `POST /api/render/export` accept `"gif"` beside mp4 and webm, rendered through a two-pass palette. `POST /api/media/capture` remuxes a browser screen or camera recording into the bin. A clip's `cutout.model` accepts `"auto"` (person when the person model finds someone, else object; needs both models); a cutout stroke may carry `region` (a normalized outline the matte shaper fills instead of the painted disc) and `t` (the source time it was resolved on), which is what `POST /api/render/smart-brush` returns for a stroke's points: `{project, clipId, time, points}` in, `{region, t}` out, 409 until `click-select` is downloaded. `clip.text` on a caption clip refits its words in place. `GET /api/models/runtime` names the active ONNX Runtime execution provider and the available list.

### v1.62.0 and v1.63.0
`POST /api/transcribe` runs Whisper in the engine as a job (`mediaId`, `sourceIn`, `duration`, `language`, `size` from tiny to large, `wordsPerCaption`, optional `audioStream`); the job's result carries `chunks` with word times, `byWord`, `model` and `provider`, the same shape the Captions panel consumes. `GET /api/transcribe/status` lists providers, sizes and which models are cached. `project.edit` adds `timeline.cut-range` (`start`, `end`): the span leaves every track of the timeline, clips inside it are removed, clips straddling it are cut into a head and a tail, and everything after moves back by the length; it is the command behind the timeline's Extract. `POST /api/speech/range` (`mediaId`, `start`, `end` in source seconds) answers the span someone speaks in near those times, found in the audio.

## MCP server

The app carries an MCP server (`formcut-engine --mcp`, module `backend/app/agent_mcp.py`) with 34 tools over stdio,
each a thin, documented wrapper over the RPC above; the full listing is generated into
`.claude/skills/formcut-mcp/sub-skills/mcp-workflows/references/tools.md`. By purpose:

- Engine and projects: `formcut_status`, `formcut_capabilities`, `formcut_catalogue`, `formcut_list_projects`,
  `formcut_create_project`, `formcut_get_project`, `formcut_edit`, `formcut_add_clip`, `formcut_set_frame`.
- Media: `formcut_import_media`, `formcut_list_media`, `formcut_media_proxy`, `formcut_find_scenes`,
  `formcut_transcribe` (sentences with their times; the small model by default), `formcut_speech_range` (RPC
  `speech.range`: `mediaId`, `start`, `end` in source seconds; answers `start`, `end` and `source`, the span someone
  speaks found in the audio, refused when there is none).
- Rendering: `formcut_render` (format, quality, rate, size, codec, ten bit, exact, audio bitrate, a loudness target
  with a true-peak ceiling), `formcut_render_audio`, `formcut_render_status`, `formcut_cancel_render`.
- Delivery checks: `formcut_qc`, `formcut_frame_check`, `formcut_speech_check`.
- Music and cutdowns: `formcut_music`, `formcut_plan_cutdown`.
- Device library: `formcut_devices` (RPC `devices.list`, optional `id`; `GET /api/devices` and
  `GET /api/devices/{id}/model`): the ten device models with their screens (inner and cover, size, aspect, suggested
  pixels, cut-outs), the parts that pose (lid, fold, stand, ranges in degrees), backlight and finishes.
- Device clips: `formcut_device` adds one on a new track (a clip of kind `device`, through `clip.add`) or changes one
  (the `clip.device` edit: a patch merged into the clip's `device` block, `camera`, `pose` and `screens` key by key,
  null removing a key, the result checked against the library). The block: `id`, `finish`, `screens.inner` and
  `screens.cover` (each `mediaId` or `timelineId`, `offset` in seconds, `fit` cover or contain), `pose` (lid, fold,
  stand in degrees, within the device's ranges), `camera` (yaw, pitch, distance with 1 framing the device, fov, roll,
  panX, panY), `backlight`, `exposure`, `light`, `shadow`, `screenBrightness`. Each number is keyframable as
  `device.<name>` (device.yaw, device.fold, device.backlight); other `device.` names are refused.
- Camera moves: `formcut_focus_motion` (the `clip.focus-motion` edit: `areas` as `[x0, y0, x1, y1]` on the clip's
  picture in visiting order, `speed` fast, medium or slow, `loop`, optional `seed` and `margin`; the clip's scale,
  posX and posY keyframes replaced in one edit; `POST /api/focus-motion` returns the keyframes without applying them).
  On a device clip the areas are in stage fractions and the move drives the camera: device.yaw, pitch, distance
  (down to 0.1), panX and panY keyframes, each stop centred on the front-most device point under its area through the
  renderer's own camera, with an alternating turn; the route takes `mode` camera, `camera`, `device` and `pose`.
- Effect packages: `formcut_package_guide`, `formcut_add_package`, `formcut_preview_package`, `formcut_list_packages`,
  `formcut_remove_package`.

`formcut_render_status` opens every reply with `state:` and a numeric `progress:` (then `file:`, or `reason:` when a job
failed or was interrupted). Tools that need a measurement of a source first (the frame, speech and cutdown checks)
start a job on the first call and say so; poll `formcut_render_status` with its id, then call again. The `cutdown`
sub-skill in `.claude/skills/formcut-mcp` walks a whole cutdown through these tools, and the `remove-speech` sub-skill
removes the footage of sentences a person names (transcribe, `formcut_speech_range`, then `timeline.cut-range`).

### v2.5.7 to v2.6.2: delivery and cutdowns

`project.export` passes every export option: `codec`, `tenBit`, `exact`, `size`, `rate` (23.976 to 60), `audioBitrate`
(kbps), `loudness` (integrated LUFS) and `truePeak` (dBTP, default -1): the mix gets one measured gain that reaches the
target without passing the ceiling. A rate more than 0.2% from the project's is sampled from the timeline at that rate.
`project.export_audio` renders the mix alone. Jobs are kept in `jobs.json` in the data folder at each status change;
after a restart finished jobs are found again and an export caught mid-render is queued again under its own id
(`interrupted`, with the reason, when it cannot be). `job.result` carries a failed job's `error` and returns a finished
job's result whole when it is not a file.

- `media.qc` (`job` or `id`, optional `edits`, `loudness`, `truePeak`): duration, frames, rate, codecs; exact and
  perceptual (mpdecimate) repeats; freezes; black and flash frames; the first and last frame against the sharpest of
  their own shot's first and last second; loudness, range and true peak; clicks at the given edits; `passed` and
  `reasons`.
- `timeline.frames` (`id`, `rate`, `fix`): each video clip's predicted repeated frames from its source's measured
  cadence; with `fix`, the smallest change that removes them (an in-point shift up to 3 source frames and a speed-up
  up to 2%, else a push of 0.10% scale an output frame) as one edit.
- `timeline.cuts` (`id`): every sounding clip's in and out point checked against its source's voice map (Silero VAD,
  the `voice-activity` model): unsafe with speech on both sides within 100 ms, the nearest pause given.
- `media.transcribe` (`id`, `size`, `language`): a whole library item transcribed as a job.
- `media.music` (`id`, optional `outFrom`, `outTo`): tempo, beat, bar, first beat, final hit; with an out-point range,
  joins a whole number of bars apart whose ends are outside speech. `media.beats` takes its tempo from the same grid.
- `media.cutdowns` (`id`, `length`, `top`): ranked scripts of the length with their exact source segments, bars and
  pauses (whole sentences, an opener that can stand first, bar-aligned joins with natural pauses, music bridges, the
  call to action last on the button); one job first measures what is missing (sentences, voice map, music map).

## Form functions

`form-functions.json` at the repository root declares formcut's Form functions for NodeMode's hub (format
`form-functions`, version 1): typed files in, typed files out, no window and no engine server. Each `entry` is a
callable in `backend/app/functions/`, `fn(inputs, params, out_dir) -> dict`: `inputs` maps each input name to a local
file, the result maps each output name to a file written inside `out_dir`, and a refusal or failure raises
`FunctionError` with a short message. Params are checked against the manifest's schema first, defaults filled in.

- `transcribe` (`media`, a video or audio file) writes `transcript.json` (model, size, language, provider, duration,
  and segments of start, end, text and words, each word with start and end) and `subtitles.srt` (the caption chunks
  the Captions panel lays out). Params: `model` tiny, base, small, medium or large (default tiny), `language` en,
  auto or a language code (default en; anything but en runs the multilingual model). It is the engine's own
  transcriber (`transcribe.py`), with the model fetched once by the pinned hub fetcher into the models folder.
- `render_project` (`project`, a `.fc` package or a `.fmc` file) writes `video.<format>`. Params: `format` mp4, webm
  or gif (default mp4), `quality` high, medium or low (default high). It is the export behind `POST /api/render/export`
  (`render_api.export_media`), run in the calling process. A `.fc` brings its media; a `.fmc` reads each media file
  only at its path relative to the `.fmc`, which must stay inside the `.fmc`'s folder (Collect Files makes such a
  folder). A clip naming media that did not come with the project is refused, and an mp4 is refused rather than
  fetching OpenH264 when the FFmpeg has no H.264 encoder.

From a shell, inside `backend/`:

```sh
python -m app.functions run transcribe --inputs '{"media": "talk.mp4"}' --params '{"model": "base"}' --out out
python -m app.functions run render_project --inputs '{"project": "cut.fc"}' --params '{"format": "webm"}' --out out
python -m app.functions manifest --write
```

`run` prints the result as one JSON line, or the error on stderr with exit status 1. Imported before the rest of the
engine with no `FORMCUT_DATA_DIR` set, the package gives the engine a private temporary data folder, removed at exit,
so a function never adds to a person's library. After changing a function's declaration in
`backend/app/functions/contract.py`, run `manifest --write`; `tests/test_form_functions.py` fails while the file
drifts.
