"""formcut MCP server.

An MCP server in front of the local formcut engine, so an agent can build, edit,
render and collect a video project without touching the interface.

Design decisions, and why:

- Workflow tools, not endpoint coverage. The engine has eighty routes; an agent
  needs a dozen verbs. Each tool here is a task someone would ask for ("add a
  clip", "render this and tell me when it is done"), because a tool surface that
  mirrors an API makes the agent assemble the workflow itself, badly.
- Explicit handles. Project ids, media ids and job ids are returned as text the
  agent can pass back. Nothing is remembered between calls, so a dropped
  connection loses no state and two agents cannot corrupt each other's view.
- Optimistic concurrency is surfaced, not hidden. Edits carry the revision the
  agent last saw; a stale revision returns the current one with an instruction to
  re-read, which is the engine's own contract.
- Errors are results, not exceptions. A failure returns text naming the recovery
  action ("the engine is not running: start it with ./formcut"), because an agent
  can act on that and cannot act on a stack trace.

- It drives the formcut that is running. The installed app runs this server as
  `formcut-engine --mcp`, so Claude Code, Codex, Cursor or any MCP client can
  launch it with nothing else installed; from the repository,
  mcp/formcut_mcp.py launches the same module. Each call finds the engine
  afresh: FORMCUT_ENGINE if set, else the address the running app published
  in engine.json in formcut's data folder (see discovery.py), else the address
  a source run uses. Quitting and reopening formcut breaks no connection.

Built on the official MCP SDK (mcp 2.2, whose server class is MCPServer), which
answers both the 2025-11-25 protocol and the stateless 2026-07-28 revision, so
older and newer clients connect alike. Transport is stdio, which is what a
desktop client launches; nothing here writes to stdout but the protocol.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Annotated, Any

import httpx
from mcp.server.mcpserver import Image, MCPServer
from pydantic import Field

SOURCE_RUN = "http://127.0.0.1:8040"


def _engine() -> str:
    """The engine to drive, found afresh on every call."""
    configured = os.environ.get("FORMCUT_ENGINE", "").strip()
    if configured:
        return configured.rstrip("/")
    from .discovery import running_engine

    return running_engine() or SOURCE_RUN


SESSION_NAME = os.environ.get("FORMCUT_MCP_SESSION", "mcp")
TIMEOUT = float(os.environ.get("FORMCUT_MCP_TIMEOUT", "120"))
HEADERS = {"x-formcut-local": "1"}

mcp = MCPServer(
    name="formcut",
    title="formcut video editor",
    version="1.0.0",
    instructions=(
        "Drive the local formcut video editor. Typical order: formcut_status to check the engine, "
        "formcut_import_media for each asset, formcut_create_project, formcut_add_clip for each clip, "
        "then formcut_render and formcut_render_status until it reports done, which carries the output "
        "path. Every call returns the handles needed by the next one; nothing is remembered here. "
        "Edits take the revision returned by the previous edit, and a stale revision is reported with "
        "the current one so you can re-read and retry."
    ),
)

_session: dict[str, str] = {}


def _explain(error: Exception) -> str:
    """Turn a transport failure into something an agent can act on."""
    if isinstance(error, httpx.ConnectError):
        return (
            f"formcut is not running (nothing answered at {_engine()}). Open the formcut app, or start it "
            "with ./formcut in the repository, then try again. FORMCUT_ENGINE names another address."
        )
    if isinstance(error, httpx.TimeoutException):
        return (
            f"The engine at {_engine()} did not answer within {TIMEOUT:.0f} s. A long render is "
            "normal: submit with formcut_render and poll formcut_render_status instead of waiting."
        )
    return f"Could not reach the engine at {_engine()}: {error.__class__.__name__}: {error}"


def _rest(method: str, path: str, payload: dict | None = None) -> tuple[bool, Any]:
    try:
        with httpx.Client(timeout=TIMEOUT, headers=HEADERS) as client:
            response = client.request(method, f"{_engine()}{path}", json=payload)
    except httpx.HTTPError as error:
        return False, _explain(error)
    if response.status_code >= 400:
        detail = ""
        try:
            detail = str(response.json().get("detail", ""))
        except ValueError:
            detail = response.text[:200]
        return False, f"The engine refused {method} {path}: {response.status_code} {detail}".strip()
    if response.status_code == 204 or not response.content:
        return True, {}
    try:
        return True, response.json()
    except ValueError:
        return True, {}


def _session_id() -> str | None:
    """Identify this server to the engine once, so the app shows who is driving."""
    if "id" in _session:
        return _session["id"]
    ok, result = _rpc("session.hello", {"name": SESSION_NAME, "agent": "formcut-mcp/1.0"}, identify=False)
    if ok and isinstance(result, dict) and result.get("id"):
        _session["id"] = str(result["id"])
        return _session["id"]
    return None


def _rpc(method: str, params: dict | None = None, identify: bool = True, timeout: float = TIMEOUT) -> tuple[bool, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    params = dict(params or {})
    if identify:
        session = _session_id()
        if session:
            params["session"] = session
    if params:
        body["params"] = params
    try:
        with httpx.Client(timeout=timeout, headers=HEADERS) as client:
            response = client.post(f"{_engine()}/api/rpc", json=body)
    except httpx.HTTPError as error:
        return False, _explain(error)
    try:
        reply = response.json()
    except ValueError:
        return False, f"The engine returned a non-JSON reply to {method} (HTTP {response.status_code})."
    if "error" in reply:
        return False, f"{method} was refused: {reply['error'].get('message', 'unknown reason')}"
    return True, reply.get("result")


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)


@mcp.tool(
    name="formcut_status",
    description=(
        "Check that the local formcut engine is running and report its version, how many projects and "
        "media items it holds, and what the effect catalogue offers. Call this first when a formcut task "
        "starts, because every other tool needs the engine up."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_status() -> str:
    ok, health = _rest("GET", "/api/health")
    if not ok:
        return health
    _, projects = _rest("GET", "/api/projects")
    _, media = _rest("GET", "/api/media")
    ok_caps, caps = _rpc("capabilities")
    lines = [
        f"engine {health.get('status', 'unknown')}, version {health.get('version', 'unknown')} at {_engine()}",
        f"projects: {len(projects) if isinstance(projects, list) else 0}",
        f"media items: {len(media) if isinstance(media, list) else 0}",
    ]
    if ok_caps and isinstance(caps, dict):
        lines.append(f"automation methods: {len(caps.get('methods', []))}")
    session = _session_id()
    if session:
        lines.append(f"this server is registered with the engine as session {session[:8]} named {SESSION_NAME}")
    return "\n".join(lines)


@mcp.tool(
    name="formcut_list_media",
    description=(
        "List the media in the formcut library with each item's id, name, kind and duration. Use it to find "
        "the media id an existing asset already has, before importing the same file again."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_list_media() -> str:
    ok, items = _rpc("media.list")
    if not ok:
        return items
    if not items:
        return "The library is empty. Import a file with formcut_import_media."
    rows = [
        f"{item['id']}  {item.get('kind', '?'):5}  {round(item.get('duration') or 0, 2):>8} s  {item.get('name', '')}" for item in items
    ]
    return "id, kind, duration, name:\n" + "\n".join(rows)


@mcp.tool(
    name="formcut_import_media",
    description=(
        "Import a local video, audio or image file into the formcut library and return its media id, kind and "
        "duration. The original file is copied, not moved. Pass the media id to formcut_add_clip to put it on "
        "a timeline."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_import_media(
    path: Annotated[str, Field(description="Absolute path to a file on the machine running the engine")],
) -> str:
    ok, item = _rpc("media.import", {"path": path})
    if not ok:
        return item
    return (
        f"imported {item.get('name')} as media {item.get('id')}\nkind {item.get('kind')}, duration {round(item.get('duration') or 0, 2)} s"
    )


@mcp.tool(
    name="formcut_create_project",
    description=(
        "Create a formcut project and return its id and revision. Frame size and rate default to 1920x1080 at "
        "30 fps and can be set here or later with formcut_set_frame. The revision is the number later edits "
        "must carry."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_create_project(
    title: Annotated[str, Field(description="Project title as it appears in formcut")] = "Untitled project",
    width: Annotated[int, Field(ge=16, le=7680, description="Frame width in pixels")] = 1920,
    height: Annotated[int, Field(ge=16, le=4320, description="Frame height in pixels")] = 1080,
    fps: Annotated[int, Field(ge=1, le=240, description="Frames per second")] = 30,
) -> str:
    ok, project = _rpc("project.create", {"title": title})
    if not ok:
        return project
    project_id, revision = project.get("id"), project.get("revision")
    if (width, height, fps) != (1920, 1080, 30):
        ok, edited = _rpc(
            "project.edit",
            {
                "id": project_id,
                "revision": revision,
                "commands": [{"op": "project.settings", "patch": {"width": width, "height": height, "fps": fps}}],
            },
        )
        if not ok:
            return f"created project {project_id} but the frame change failed: {edited}"
        revision = edited.get("revision")
    return (
        f"created project {project_id} titled {title}\n"
        f"frame {width}x{height} at {fps} fps, revision {revision}\n"
        "pass this id and revision to formcut_add_clip"
    )


@mcp.tool(
    name="formcut_get_project",
    description=(
        "Read a formcut project: its title, frame, duration, current revision and the clips on each track. Use "
        "it to recover the revision after a stale-revision refusal, or to see what a project already contains."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_get_project(
    project_id: Annotated[str, Field(description="Project id from formcut_create_project or formcut_list_projects")],
) -> str:
    ok, project = _rpc("project.get", {"id": project_id})
    if not ok:
        return project
    timeline = project.get("timelines", [{}])[project.get("activeTimeline", 0)]
    lines = [
        f"{project.get('title')}  revision {project.get('revision')}",
        (
            f"frame {project.get('width')}x{project.get('height')} at {project.get('fps')} fps, "
            f"duration {round(project.get('duration') or 0, 2)} s"
        ),
    ]
    for index, track in enumerate(timeline.get("tracks", [])):
        clips = (
            ", ".join(
                f"{clip.get('label', clip.get('id'))} at {clip.get('start')}s for {clip.get('duration')}s"
                + (
                    f" (media {clip['mediaId']}, source in {clip.get('sourceIn') or 0}s, speed {clip.get('speed') or 1})"
                    if clip.get("mediaId")
                    else ""
                )
                for clip in track.get("clips", [])
            )
            or "empty"
        )
        lines.append(f"track {index} ({track.get('name', 'track')}): {clips}")
    return "\n".join(lines)


@mcp.tool(
    name="formcut_media_proxy",
    description=(
        "Check or build the editing proxy for a media item. Proxies are smaller copies that make scrubbing and "
        "previewing fast on large or awkwardly encoded footage; exports always read the original, never the proxy. "
        "Pass build=true to start one if it is missing. Returns the proxy's state and size."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_media_proxy(
    media_id: Annotated[str, Field(description="Media id from formcut_list_media")],
    build: Annotated[bool, Field(description="Start building the proxy if there is not one")] = False,
) -> str:
    ok, state = _rpc("media.proxy", {"id": media_id, "build": build})
    if not ok:
        return state
    where = state.get("state", "unknown")
    if where == "ready":
        size = state.get("bytes")
        return f"Proxy ready for {media_id}" + (f", {size} bytes" if size else "")
    if where == "building":
        return f"Proxy for {media_id} is building, {round(float(state.get('progress') or 0) * 100)}% done"
    if build:
        return f"Proxy for {media_id} has been queued"
    return f"No proxy for {media_id}. Call again with build=true to make one."


@mcp.tool(
    name="formcut_find_scenes",
    description=(
        "Find the cuts in a piece of footage, so a long recording can be split into its shots. Returns each cut's "
        "time in seconds and the segments between them. Nothing is changed: to act on it, add each segment kept "
        "with formcut_add_clip (source_in at its start), or split a clip at the cut times with formcut_edit "
        "(the clip.split operation)."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_find_scenes(
    media_id: Annotated[str, Field(description="Media id from formcut_list_media")],
    sensitivity: Annotated[float, Field(ge=0, le=1, description="Higher finds more cuts")] = 0.5,
) -> str:
    ok, found = _rpc("media.scenes", {"id": media_id, "sensitivity": sensitivity})
    if not ok:
        return found
    cuts = found.get("cuts") or []
    if not cuts:
        return "No scene changes found; this looks like one continuous shot."
    lines = [f"{len(cuts)} cut(s):"]
    lines += [f"  {round(float(cut.get('at', 0)), 2)} s" for cut in cuts[:40]]
    return "\n".join(lines)


@mcp.tool(
    name="formcut_list_projects",
    description="List the saved formcut projects with their ids and titles, so a project can be opened or edited by id.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_list_projects() -> str:
    ok, projects = _rpc("project.list")
    if not ok:
        return projects
    if not projects:
        return "No saved projects. Create one with formcut_create_project."
    return "\n".join(f"{item.get('id')}  {item.get('title')}" for item in projects)


@mcp.tool(
    name="formcut_add_clip",
    description=(
        "Put an imported media item on a project timeline and return the new revision. Give the media id from "
        "formcut_import_media, the track index (0 is the top track), where the clip starts in seconds, how long "
        "it runs, and optionally where in the source to start from. Returns the revision the next edit must carry."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_add_clip(
    project_id: Annotated[str, Field(description="Project id")],
    revision: Annotated[int, Field(ge=0, description="Revision last seen for this project")],
    media_id: Annotated[str, Field(description="Media id from formcut_import_media or formcut_list_media")],
    start: Annotated[float, Field(ge=0, description="Where the clip begins on the timeline, in seconds")] = 0.0,
    duration: Annotated[float, Field(gt=0, description="How long the clip runs, in seconds")] = 5.0,
    track: Annotated[int, Field(ge=0, le=16, description="Track index, 0 is the top track")] = 0,
    source_in: Annotated[float, Field(ge=0, description="Where to start inside the source media, in seconds")] = 0.0,
    label: Annotated[str, Field(description="Clip label, defaults to the media name")] = "",
) -> str:
    ok, media = _rpc("media.list")
    kind, name = "video", label
    if ok and isinstance(media, list):
        found = next((item for item in media if item.get("id") == media_id), None)
        if found is None:
            return (
                f"No media with id {media_id}. Run formcut_list_media to see what the library holds, or "
                "import the file first with formcut_import_media."
            )
        kind = found.get("kind", "video")
        name = label or found.get("name", media_id)
    clip = {
        "id": os.urandom(8).hex(),
        "kind": kind,
        "label": name,
        "mediaId": media_id,
        "start": start,
        "duration": duration,
        "sourceIn": source_in,
    }
    ok, edited = _rpc(
        "project.edit", {"id": project_id, "revision": revision, "commands": [{"op": "clip.add", "track": track, "clip": clip}]}
    )
    if not ok:
        return f"{edited}\nIf the revision was stale, call formcut_get_project to read the current one and retry."
    return (
        f"added {name} to track {track} at {start} s for {duration} s\n"
        f"project {project_id} is now revision {edited.get('revision')}, duration "
        f"{round(edited.get('duration') or 0, 2)} s"
    )


@mcp.tool(
    name="formcut_set_frame",
    description=(
        "Change a project's frame size and rate, and return the new revision. Use it when the output format "
        "differs from the default 1920x1080 at 30 fps."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_set_frame(
    project_id: Annotated[str, Field(description="Project id")],
    revision: Annotated[int, Field(ge=0, description="Revision last seen for this project")],
    width: Annotated[int, Field(ge=16, le=7680, description="Frame width in pixels")],
    height: Annotated[int, Field(ge=16, le=4320, description="Frame height in pixels")],
    fps: Annotated[int, Field(ge=1, le=240, description="Frames per second")] = 30,
) -> str:
    ok, edited = _rpc(
        "project.edit",
        {
            "id": project_id,
            "revision": revision,
            "commands": [{"op": "project.settings", "patch": {"width": width, "height": height, "fps": fps}}],
        },
    )
    if not ok:
        return f"{edited}\nCall formcut_get_project for the current revision and retry."
    return f"frame set to {width}x{height} at {fps} fps, revision {edited.get('revision')}"


@mcp.tool(
    name="formcut_render",
    description=(
        "Start rendering a project to a file and return a job id. Rendering takes minutes, so this returns "
        "immediately: poll formcut_render_status with the job id until it reports done, which carries the output "
        "path. Format is mp4, webm or gif; quality is low, medium or high. Optional: rate (23.976, 24, 25, 29.97, "
        "30, 50, 59.94 or 60; the project's own when unset), size, codec, ten_bit, exact (an intra-only master), "
        "audio_bitrate in kbps (192, 256 or 320), and a loudness target in LUFS with a true-peak ceiling in dBTP "
        "(one measured gain on the mix, no compression)."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_render(
    project_id: Annotated[str, Field(description="Project id to render")],
    file_format: Annotated[str, Field(description="Output container: mp4, webm or gif")] = "mp4",
    quality: Annotated[str, Field(description="Encoder ladder: low, medium or high")] = "high",
    rate: Annotated[str | None, Field(description="Output frame rate, e.g. 23.976 or 24; the project's when unset")] = None,
    transparent: Annotated[
        bool, Field(description="No background, alpha kept: file_format mov (ProRes 4444), webm (VP9 alpha) or png (zip)")
    ] = False,
    size: Annotated[str | None, Field(description="Output size preset (see formcut_capabilities); the project's when unset")] = None,
    codec: Annotated[str | None, Field(description="Video codec, e.g. h264, hevc, av1, vp9; the container's default when unset")] = None,
    ten_bit: Annotated[bool, Field(description="Ten-bit video where the codec carries it")] = False,
    exact: Annotated[bool, Field(description="An intra-only master for frame-exact editing elsewhere")] = False,
    audio_bitrate: Annotated[int | None, Field(description="Audio bitrate in kbps, e.g. 192, 256 or 320")] = None,
    loudness: Annotated[float | None, Field(description="Integrated loudness target in LUFS, e.g. -14, -16 or -23")] = None,
    true_peak: Annotated[float, Field(description="True-peak ceiling in dBTP the loudness gain never passes")] = -1.0,
) -> str:
    if transparent and file_format not in ("mov", "webm", "png"):
        return "a transparent export is mov (ProRes 4444), webm (VP9 with alpha) or png (a zip of frames)"
    if not transparent and file_format not in ("mp4", "webm", "gif"):
        return "format must be mp4, webm or gif"
    if quality not in ("low", "medium", "high"):
        return "quality must be low, medium or high"
    options = {
        "rate": rate,
        "size": size,
        "codec": codec,
        "tenBit": ten_bit or None,
        "exact": exact or None,
        "transparent": transparent or None,
    }
    options |= {"audioBitrate": audio_bitrate, "loudness": loudness, "truePeak": true_peak if loudness is not None else None}
    params = {"id": project_id, "format": file_format, "quality": quality} | {k: v for k, v in options.items() if v is not None}
    ok, job = _rpc("project.export", params)
    if not ok:
        return job
    job_id = job.get("job_id")
    chosen = ", ".join(f"{k} {v}" for k, v in options.items() if v is not None)
    return (
        f"render started as job {job_id} ({file_format}, {quality}{', ' + chosen if chosen else ''})\n"
        "poll formcut_render_status with this job id; a minute between polls is reasonable"
    )


@mcp.tool(
    name="formcut_render_status",
    description=(
        "Report a render's progress, and when it is finished give the output file path. Also reports a cancelled "
        "or failed render with the reason. Poll this after formcut_render."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_render_status(
    job_id: Annotated[str, Field(description="Job id from formcut_render")],
) -> str:
    ok, state = _rpc("job.result", {"id": job_id})
    if not ok:
        return state
    if state.get("ready"):
        return (
            f"state: done\nprogress: 1.000\nfile: {state.get('file')}\nname: {state.get('name')}\n"
            f"type: {state.get('media_type')}\nalso fetchable from {_engine()}{state.get('url')}"
        )
    status = state.get("status", "unknown")
    progress = float(state.get("progress") or 0)
    if status in ("cancelled", "error", "interrupted"):
        reason = state.get("error") or state.get("message") or "not given"
        return f"state: {status}\nprogress: {progress:.3f}\nreason: {reason}\nStart a new one with formcut_render when the cause is fixed."
    return f"state: {status}\nprogress: {progress:.3f}\nrender {status}, {round(progress * 100)}% done. Poll again shortly."


@mcp.tool(
    name="formcut_plan_cutdown",
    description=(
        "Plan cutdowns of a master: ranked scripts of the given length (seconds) from its mix, each with its exact "
        "source segments, the bars jumped at each join and the pause each leaves. Every script: whole sentences, "
        "joins a whole number of bars apart outside speech with natural pauses (a music bridge such as an end-card "
        "wipe allowed), the closing call to action last, ending on the music's button, the length exact. Ranked by "
        "natural pauses, opening the film, fewer joins; choosing among them is editorial (see the cutdown "
        "sub-skill). The first call on a new master starts a measuring job: poll formcut_render_status, then call again."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_plan_cutdown(
    media_id: Annotated[str, Field(description="The master (or its mix) in the library")],
    length: Annotated[float, Field(description="Target length in seconds, e.g. 15 or 30")] = 15.0,
    top: Annotated[int, Field(description="How many scripts to return, best first")] = 10,
) -> str:
    ok, result = _rpc("media.cutdowns", {"id": media_id, "length": length, "top": top})
    if not ok:
        return result
    return json.dumps(result, indent=1)


@mcp.tool(
    name="formcut_music",
    description=(
        "A library item's music grid: tempo (BPM), beat and bar length, first beat, and the final hit (the chord a "
        "spot can end on). With out_from (and out_to), also joins a whole number of bars apart: an out-point in that "
        "range and an in-point later, both outside speech (formcut_speech_check's rule), so the music runs on and no "
        "sentence is cut. The downbeat is reported as the music's first beat; it is not detected from the audio."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_music(
    media_id: Annotated[str, Field(description="The library item carrying the music (a mix or a music track)")],
    out_from: Annotated[float | None, Field(description="Earliest out-point for joins, in seconds of this media")] = None,
    out_to: Annotated[float | None, Field(description="Latest out-point for joins; out_from when unset")] = None,
) -> str:
    params = {"id": media_id} | ({"outFrom": out_from} if out_from is not None else {}) | ({"outTo": out_to} if out_to is not None else {})
    ok, result = _rpc("media.music", params)
    if not ok:
        return result
    return json.dumps(result, indent=1)


@mcp.tool(
    name="formcut_transcribe",
    description=(
        "Transcribe a library item's speech with formcut's local Whisper (ONNX). Call with media_id to start (returns "
        "a job id), then with that job_id to collect the sentences with their start and end times. size is tiny, "
        "base, small (default), medium or large; small covers a music-bedded voice-over far better than base. "
        "Sentence times are reliable; word times inside a sentence are not cut points: check cuts with "
        "formcut_speech_check."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_transcribe(
    media_id: Annotated[str | None, Field(description="Library item to transcribe (starts a job)")] = None,
    size: Annotated[str, Field(description="Model size: tiny, base, small, medium or large")] = "small",
    job_id: Annotated[str | None, Field(description="A transcription job's id, to collect its sentences")] = None,
) -> str:
    if job_id:
        ok, state = _rpc("job.result", {"id": job_id})
        if not ok:
            return state
        if not state.get("ready"):
            reason = f", {state['error']}" if state.get("error") else ""
            return f"state: {state.get('status')}\nprogress: {float(state.get('progress') or 0):.3f}{reason}"
        result = state.get("result") or {}
        sentences = []
        for chunk in result.get("chunks", []):
            sentences.append({"start": chunk.get("start"), "end": chunk.get("end"), "text": str(chunk.get("text", "")).strip()})
        return json.dumps({"model": result.get("model"), "sentences": sentences}, indent=1)
    if not media_id:
        return "give a media_id to start, or the job_id of a transcription to collect"
    if size not in ("tiny", "base", "small", "medium", "large"):
        return "size must be tiny, base, small, medium or large"
    ok, job = _rpc("media.transcribe", {"id": media_id, "size": size})
    if not ok:
        return job
    return f"transcription started as job {job.get('job_id')}\ncall formcut_transcribe again with this job_id to collect it"


@mcp.tool(
    name="formcut_speech_range",
    description=(
        "The span someone speaks in near two times of a library item, found in the audio (voice-activity model when "
        "installed, else loudness): from the speech onset to the speech offset, in source seconds, with the method "
        "used as source. Give start and end in the media's own seconds (a sentence's times from formcut_transcribe, "
        "mapped through the clip's source in-point). Never cut on caption or word times directly: use this range, "
        "then cut it on the timeline with formcut_edit timeline.cut-range. Refused when no speech is found there."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_speech_range(
    media_id: Annotated[str, Field(description="Library item whose audio is read")],
    start: Annotated[float, Field(description="Near the sentence start, in seconds of this media", ge=0)],
    end: Annotated[float, Field(description="Near the sentence end, in seconds of this media", ge=0)],
) -> str:
    ok, result = _rpc("speech.range", {"mediaId": media_id, "start": start, "end": end})
    if not ok:
        return result
    return json.dumps(result, indent=1)


@mcp.tool(
    name="formcut_speech_check",
    description=(
        "Before rendering: check every sounding clip's in and out point on the active timeline for cutting through "
        "speech, music bed or not (a voice-activity model: unsafe when someone is speaking on both sides of the cut "
        "within 100 ms). Unsafe cuts come back with the nearest pause to move them into. The first call on a new "
        "source starts a measuring job: poll formcut_render_status with its id, then call again. Needs the "
        "voice-activity model (Settings, Models, or POST /api/models/voice-activity/download on the engine)."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_speech_check(
    project_id: Annotated[str, Field(description="Project id; its active timeline is checked")],
) -> str:
    ok, result = _rpc("timeline.cuts", {"id": project_id})
    if not ok:
        return result
    return json.dumps(result, indent=1)


@mcp.tool(
    name="formcut_devices",
    description=(
        "The device library: ten photoreal device models (phones, tablets, a flip and two folds, two laptops and a "
        "2-in-1) for device mockups. Each lists its screens a clip can be shown on (the inner display, and on folding "
        "devices the cover display, with size, aspect, suggested pixels and cut-outs), the parts that pose (lid, fold, "
        "stand, with ranges in degrees), whether the keyboard is backlit, and its finishes. Give an id for one device."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_devices(
    device_id: Annotated[str | None, Field(description="One device's id, e.g. fold-open; omit for all")] = None,
) -> str:
    ok, result = _rpc("devices.list", {"id": device_id} if device_id else {})
    if not ok:
        return result
    items = [result] if device_id else result["devices"]
    lines = [] if device_id else [f"{len(items)} devices (library {result['version']}, contract {result['contract']})"]
    for item in items:
        screens = "; ".join(
            f"{s['slot']} {s['pixels'][0]}x{s['pixels'][1]} (aspect {s['aspect']})"
            + (f", cut-out {s['cutouts'][0]['shape']}" if s["cutouts"] else "")
            for s in item["screens"]
        )
        poses = ", ".join(f"{a['name']} {a['closedDeg']} to {a['maxDeg']} deg" for a in item["articulations"]) or "none"
        lines.append(
            f"{item['id']} ({item['kind']}, {item['style']}): screens {screens}; poses {poses}; "
            f"backlit keyboard {'yes' if item['backlight'] else 'no'}; finishes {', '.join(sorted(item['finishes']))}"
        )
    return "\n".join(lines)


@mcp.tool(
    name="formcut_device",
    description=(
        "Add a device mockup clip, or change one. With device_id (from formcut_devices) it adds a device clip on a new "
        "track; with clip_id it changes that clip. Each screen (inner, and cover on folding devices) shows a media id or "
        'a timeline id, fitted by cover (crop to fill) or contain. pose sets parts in degrees, e.g. {"fold": 90} or '
        '{"lid": 100, "stand": 40}; camera sets yaw, pitch, distance (1 frames the device), fov, roll, panX, panY; '
        "backlight is the keyboard glow, 0 to about 1.5. Every number can then be keyframed as device.<name> "
        "(device.yaw, device.fold, device.backlight). One undoable edit."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_device(
    project_id: Annotated[str, Field(description="Project id")],
    revision: Annotated[int, Field(ge=0, description="Revision last seen for this project")],
    device_id: Annotated[str | None, Field(description="Library device to add, or to switch an existing clip to")] = None,
    clip_id: Annotated[str | None, Field(description="An existing device clip to change")] = None,
    start: Annotated[float, Field(ge=0, description="Where a new clip starts, seconds")] = 0.0,
    duration: Annotated[float, Field(gt=0, description="A new clip's length, seconds")] = 5.0,
    finish: Annotated[str | None, Field(description="One of the device's finishes")] = None,
    inner_media: Annotated[str | None, Field(description="Media shown on the inner screen")] = None,
    inner_timeline: Annotated[str | None, Field(description="Timeline shown on the inner screen")] = None,
    cover_media: Annotated[str | None, Field(description="Media shown on the cover screen")] = None,
    cover_timeline: Annotated[str | None, Field(description="Timeline shown on the cover screen")] = None,
    fit: Annotated[str, Field(description="cover or contain")] = "cover",
    pose: Annotated[dict | None, Field(description="Parts in degrees: lid, fold, stand")] = None,
    camera: Annotated[dict | None, Field(description="yaw, pitch, distance, fov, roll, panX, panY")] = None,
    backlight: Annotated[float | None, Field(ge=0, le=3, description="Keyboard backlight level")] = None,
    template: Annotated[
        str | None, Field(description="A ready animation: hero, push, reveal (flip, fold), opening (laptop, 2-in-1), stand (2-in-1)")
    ] = None,
) -> str:
    patch: dict = {k: v for k, v in {"finish": finish, "pose": pose, "camera": camera, "backlight": backlight}.items() if v is not None}
    screens = {}
    for slot, media, timeline in (("inner", inner_media, inner_timeline), ("cover", cover_media, cover_timeline)):
        if media or timeline:
            screens[slot] = {"mediaId": media, "fit": fit} if media else {"timelineId": timeline, "fit": fit}
    if screens:
        patch["screens"] = screens
    if clip_id:
        if device_id:
            patch["id"] = device_id
        commands = [{"op": "clip.device", "clipId": clip_id, "patch": patch}]
        new_id = clip_id
    else:
        if not device_id:
            return "Give device_id (see formcut_devices) to add a device clip, or clip_id to change one"
        ok, project = _rpc("project.get", {"id": project_id})
        if not ok:
            return project
        tracks = project["timelines"][project.get("activeTimeline", 0)]["tracks"]
        new_id = uuid.uuid4().hex
        clip = {
            "id": new_id,
            "kind": "device",
            "label": device_id,
            "start": start,
            "duration": duration,
            "device": {"id": device_id, **patch},
        }
        commands = [{"op": "track.add", "name": "Device"}, {"op": "clip.add", "track": len(tracks), "clip": clip}]
    if template:
        from .device_templates import keyframes as template_keys
        from .device_templates import touched
        from .devices import device as library_device

        ok, project = _rpc("project.get", {"id": project_id})
        if not ok:
            return project
        found = next((c for tl in project["timelines"] for t in tl["tracks"] for c in t["clips"] if c["id"] == clip_id), None)
        if clip_id and not found:
            return f"No clip {clip_id}"
        which = device_id or (found or {}).get("device", {}).get("id")
        length = float(found["duration"]) if found else duration
        try:
            made = template_keys(template, library_device(str(which)), length)
        except (KeyError, ValueError) as exc:
            return str(exc)
        replaced = touched(made)
        kept = [{**k, "props": {p: v for p, v in k["props"].items() if p not in replaced}} for k in ((found or {}).get("keyframes") or [])]
        merged = sorted([k for k in kept if k["props"]] + made, key=lambda k: k["t"])
        if clip_id:
            commands.append({"op": "clip.update", "clipId": clip_id, "patch": {"keyframes": merged}})
        else:
            commands[-1]["clip"]["keyframes"] = merged
    ok, result = _rpc("project.edit", {"id": project_id, "revision": revision, "commands": commands})
    if not ok:
        return result
    return f"device clip {new_id} {'changed' if clip_id else 'added'}; project revision {result.get('revision')}"


@mcp.tool(
    name="formcut_focus_motion",
    description=(
        "Compose a camera move from focus areas on a clip: each area is a rectangle on the clip's own picture as "
        "[x0, y0, x1, y1] in 0 to 1; the move opens wide, frames each area in turn (centred, filling all but the margin, "
        "never showing an empty edge the wide shot did not) and holds on it, and with loop returns to the wide shot so "
        "it repeats. Written as the clip's scale, posX and posY keyframes in one undoable edit, editable afterwards. "
        "speed is fast, medium or slow; a seed shuffles the order the areas are visited. On a device clip the areas are "
        "on the stage and the move drives the device camera in 3D (turn, tilt, distance and pan keyframes, each area "
        "centred on the device point under it)."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_focus_motion(
    project_id: Annotated[str, Field(description="Project id")],
    revision: Annotated[int, Field(ge=0, description="Revision last seen for this project")],
    clip_id: Annotated[str, Field(description="The clip to move over")],
    areas: Annotated[list[list[float]], Field(description="Focus areas in visiting order, each [x0, y0, x1, y1] in 0 to 1")],
    speed: Annotated[str, Field(description="fast, medium or slow")] = "medium",
    loop: Annotated[bool, Field(description="End on the wide shot so the move repeats cleanly")] = False,
    seed: Annotated[int | None, Field(description="Shuffle the visiting order with this seed")] = None,
) -> str:
    if speed not in ("fast", "medium", "slow"):
        return "speed must be fast, medium or slow"
    command = {"op": "clip.focus-motion", "clipId": clip_id, "areas": areas, "speed": speed, "loop": loop}
    if seed is not None:
        command["seed"] = seed
    ok, result = _rpc("project.edit", {"id": project_id, "revision": revision, "commands": [command]})
    if not ok:
        return result
    return f"focus move written on clip {clip_id}; project revision {result.get('revision')}"


@mcp.tool(
    name="formcut_frame_check",
    description=(
        "Before rendering: predict which video clips on the active timeline would show a repeated frame at an output "
        "rate, from each source's measured cadence (a 60p master can carry 24, 25 and 30p footage padded with "
        "duplicates). With fix, apply per clip the smallest change that removes them: an in-point shift of up to 3 "
        "source frames and a speed-up of up to 2%, or a slow keep-alive push on a hold. The first call on a new source "
        "starts a measuring job: poll formcut_render_status with its id, then call again."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_frame_check(
    project_id: Annotated[str, Field(description="Project id; its active timeline is checked")],
    rate: Annotated[float | None, Field(description="Output frame rate; the project's when unset")] = None,
    fix: Annotated[bool, Field(description="Apply the changes that remove the predicted repeats")] = False,
) -> str:
    params = {"id": project_id, "fix": fix} | ({"rate": rate} if rate else {})
    ok, result = _rpc("timeline.frames", params)
    if not ok:
        return result
    return json.dumps(result, indent=1)


@mcp.tool(
    name="formcut_qc",
    description=(
        "Check a rendered file before delivering it: duration, frame count and rate; exact repeated frames and "
        "near duplicates (ffmpeg's mpdecimate); freezes; black and flash frames; first and last frame sharpness; "
        "integrated loudness, range and true peak; clicks at given audio edit points. Returns JSON with passed and "
        "the reasons it failed. Give a finished render's job id, or a media id."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_qc(
    job_id: Annotated[str | None, Field(description="A finished render's job id")] = None,
    media_id: Annotated[str | None, Field(description="Or a media id from the library")] = None,
    edits: Annotated[list[float] | None, Field(description="Audio edit points in seconds, to listen for clicks")] = None,
    loudness: Annotated[float | None, Field(description="Integrated loudness target in LUFS; within 1 LU passes")] = None,
    true_peak: Annotated[float, Field(description="True-peak ceiling in dBTP")] = -1.0,
) -> str:
    if not job_id and not media_id:
        return "give a finished render's job id or a media id"
    params = {"job": job_id} if job_id else {"id": media_id}
    params |= {"edits": edits or [], "truePeak": true_peak} | ({"loudness": loudness} if loudness is not None else {})
    ok, report = _rpc("media.qc", params)
    if not ok:
        return report
    head = {"passed": report.get("passed"), "reasons": report.get("reasons")}
    return json.dumps({**head, **{k: v for k, v in report.items() if k not in head}}, indent=1)


@mcp.tool(
    name="formcut_render_audio",
    description=(
        "Start rendering a project's audio mix alone (a WAV) and return a job id; poll formcut_render_status with it. "
        "For measuring or mastering the mix outside the picture render."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_render_audio(
    project_id: Annotated[str, Field(description="Project id whose mix to render")],
) -> str:
    ok, job = _rpc("project.export_audio", {"id": project_id})
    if not ok:
        return job
    return f"audio render started as job {job.get('job_id')}\npoll formcut_render_status with this job id"


@mcp.tool(
    name="formcut_cancel_render",
    description="Stop a render that is still running. The partial output is discarded.",
    annotations={"readOnlyHint": False, "destructiveHint": True, "openWorldHint": False},
)
def formcut_cancel_render(
    job_id: Annotated[str, Field(description="Job id from formcut_render")],
) -> str:
    ok, result = _rpc("job.cancel", {"id": job_id})
    if not ok:
        return result
    return f"cancellation requested for job {job_id}. Poll formcut_render_status to see it settle."


@mcp.tool(
    name="formcut_catalogue",
    description=(
        "List what the formcut renderer can apply, with the ids an edit uses: video entries (colour grades and "
        "visual effects, each with a category and group), audio chains, transitions and blend modes. Use it "
        "before naming an effect, so the id is real."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_catalogue(
    kind: Annotated[str, Field(description="Which family to list: video, audio, transitions, blendModes or all")] = "all",
    group: Annotated[str, Field(description="Optional group filter within a family, for example Blur, Adjust or Voice")] = "",
) -> str:
    ok, catalogue = _rpc("catalogue")
    if not ok:
        return catalogue
    if not isinstance(catalogue, dict):
        return _text(catalogue)
    families = list(catalogue) if kind == "all" else [kind]
    unknown = [name for name in families if name not in catalogue]
    if unknown:
        return f"No such family {unknown[0]}. The engine offers: {', '.join(catalogue)}."
    lines = []
    for family in families:
        entries = catalogue.get(family)
        if not isinstance(entries, list):
            continue
        chosen = [
            entry for entry in entries if not group or (isinstance(entry, dict) and str(entry.get("group", "")).lower() == group.lower())
        ]
        ids = [str(entry.get("id", entry)) if isinstance(entry, dict) else str(entry) for entry in chosen]
        groups = sorted({str(entry.get("group")) for entry in entries if isinstance(entry, dict) and entry.get("group")})
        head = f"{family} ({len(ids)} of {len(entries)})" if group else f"{family} ({len(ids)})"
        lines.append(f"{head}: {', '.join(ids[:60])}{' ...' if len(ids) > 60 else ''}")
        if groups and not group:
            lines.append(f"  groups: {', '.join(groups)}")
    return "\n".join(lines) or "The engine reported an empty catalogue."


@mcp.tool(
    name="formcut_edit",
    description=(
        "Apply raw edit commands to a project for anything the named tools do not cover, such as trimming, "
        "splitting, effects, keyframes or transitions, and return the new revision. Commands are the engine's own "
        "edit operations; call formcut_capabilities to see which are accepted."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_edit(
    project_id: Annotated[str, Field(description="Project id")],
    revision: Annotated[int, Field(ge=0, description="Revision last seen for this project")],
    commands_json: Annotated[
        str, Field(description='A JSON array of edit commands, for example [{"op": "clip.split", "clipId": "abc", "time": 2.0}]')
    ],
) -> str:
    try:
        commands = json.loads(commands_json)
    except ValueError as error:
        return f"commands_json is not valid JSON: {error}"
    if not isinstance(commands, list) or not commands:
        return "commands_json must be a non-empty JSON array of command objects."
    ok, edited = _rpc("project.edit", {"id": project_id, "revision": revision, "commands": commands})
    if not ok:
        return f"{edited}\nCall formcut_capabilities for the accepted operations, or formcut_get_project for the current revision."
    return f"applied {len(commands)} command(s); project is now revision {edited.get('revision')}"


# Effect packages: an agent can learn the format, add one, look at it, list and remove.


def _upload(path: str, filename: str, data: bytes) -> tuple[bool, Any]:
    try:
        with httpx.Client(timeout=TIMEOUT, headers=HEADERS) as client:
            response = client.post(f"{_engine()}{path}", files={"file": (filename, data, "application/json")})
    except httpx.HTTPError as error:
        return False, _explain(error)
    if response.status_code >= 400:
        try:
            detail = str(response.json().get("detail", ""))
        except ValueError:
            detail = response.text[:200]
        return False, f"The engine refused the package: {detail or response.status_code}"
    return True, response.json()


@mcp.tool(
    name="formcut_package_guide",
    description=(
        "Everything needed to write an effect package: the manifest format, the stack a video package is made of, "
        "every effect id with its parameters and ranges, every custom grade setting with its range, the audio "
        "filters a chain package may use, and a working example. Read it before formcut_add_package."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_package_guide(
    group: Annotated[str, Field(description="Optional effect group to list in full, for example Blur, Stylize, Distort or Texture")] = "",
) -> str:
    ok, schema = _rest("GET", "/api/packages/schema")
    if not ok:
        return schema
    lines = [
        "An effect package is a manifest (JSON). A video package is a stack: steps run in order, each blended by its amount.",
        (
            f"Manifest fields: id (matching {schema['idPattern']}), name, kind (video or audio), optional category, optional names "
            f"(a name per language: {', '.join(schema['languages'])}), and for video a stack of 1 to {schema['maxSteps']} steps."
        ),
        'A step is {"effect": id, "amount": 0 to 1, "params": {name: number}} or {"grade": {setting: number}, "amount": 0 to 1}.',
        "An effect step may also name one of the colour grades by id. Parameters left out take their defaults.",
        "Adding a package with an id you already added replaces it, so refine by re-adding. formcut's own looks cannot be replaced.",
        "",
        "Grade settings (neutral value, range):",
    ]
    lines += [f"  {key}: neutral {spec['neutral']:g}, {spec['min']:g} to {spec['max']:g}" for key, spec in schema["gradeSettings"].items()]
    lines.append("")
    groups: dict[str, list] = {}
    for effect in schema["effects"]:
        groups.setdefault(effect["group"], []).append(effect)
    for name, effects in groups.items():
        if group and name.lower() != group.lower():
            lines.append(f"{name}: {len(effects)} effects (pass group={name} to list them)")
            continue
        lines.append(f"{name}:")
        for effect in effects:
            params = ", ".join(f"{p['key']} {p['min']:g} to {p['max']:g} (default {p['default']:g})" for p in effect["parameters"])
            lines.append(f"  {effect['id']}{': ' + params if params else ''}")
    lines += [
        "",
        f"Named colour grades usable as effect steps: {', '.join(schema['grades'][:40])}{' ...' if len(schema['grades']) > 40 else ''}",
        f"Audio packages are a chain.txt of these filters only, not a stack: {', '.join(schema['audioFilters'])}. Add those as a .zip through the interface.",
        "",
        "Example:",
        json.dumps(schema["example"], indent=2, ensure_ascii=False),
        "",
        "Then formcut_add_package with the manifest, and formcut_preview_package to look at the result.",
    ]
    return "\n".join(lines)


@mcp.tool(
    name="formcut_add_package",
    description=(
        "Add a video effect package from its manifest (see formcut_package_guide). The engine checks it exactly as "
        "it checks every package and refuses it with the reason; accepted, it appears under Packages in the effects "
        "browser and can be used by id in edits. Adding the same id again replaces it."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False},
)
def formcut_add_package(
    manifest: Annotated[dict, Field(description="The package manifest: id, name, kind video, optional category and names, and its stack")],
) -> str:
    ok, result = _upload("/api/packages/import", "manifest.json", json.dumps(manifest).encode("utf-8"))
    if not ok:
        return result
    verb = "Replaced" if result.get("replaced") else "Added"
    return f"{verb} {result.get('name')} as {result.get('id')}. Look at it with formcut_preview_package, or apply it by id in an edit."


@mcp.tool(
    name="formcut_preview_package",
    description=(
        "Render an effect package, or any effect or grade id, on formcut's example picture and return the image, "
        "exactly as the effects browser shows it. Use it to judge a package and adjust its stack."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_preview_package(
    package_id: Annotated[str, Field(description="The id of a package, effect or grade")],
) -> Image | str:
    try:
        with httpx.Client(timeout=TIMEOUT, headers=HEADERS) as client:
            response = client.get(f"{_engine()}/api/catalogue/preview/effect/{package_id}")
    except httpx.HTTPError as error:
        return _explain(error)
    if response.status_code == 404:
        return f"No package, effect or grade has the id {package_id}. formcut_list_packages lists yours."
    if response.status_code >= 400:
        return f"The engine could not render {package_id}: {response.status_code}"
    return Image(data=response.content, format="png")


@mcp.tool(
    name="formcut_list_packages",
    description="List the effect packages a person has added, with their kind and category, and any that failed to load with the reason.",
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_list_packages() -> str:
    ok, result = _rest("GET", "/api/packages")
    if not ok:
        return result
    packages = result.get("packages", [])
    own = [p for p in packages if not p.get("library")]
    lines = [f"{len(own)} added package(s); formcut also has {len(packages) - len(own)} built-in looks, which cannot be changed."]
    lines += [f"  {p['id']}: {p['name']} ({p['kind']}, {p.get('category', 'Packages')})" for p in own]
    for failure in result.get("failures", []):
        lines.append(f"  failed to load {failure['package']}: {failure['reason']}")
    return "\n".join(lines)


@mcp.tool(
    name="formcut_remove_package",
    description=(
        "Remove an effect package a person added. formcut's built-in looks cannot be removed, and a package that a "
        "saved project still uses is refused, naming the projects, since they would no longer load without it."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": False},
)
def formcut_remove_package(
    package_id: Annotated[str, Field(description="The id of a package you added")],
) -> str:
    ok, result = _rest("DELETE", f"/api/packages/{package_id}")
    return f"Removed {package_id}." if ok else result


@mcp.tool(
    name="formcut_capabilities",
    description=(
        "Report the engine's automation surface: the methods it accepts, the project properties an edit may set "
        "and the edit operation names. Use it when an edit is refused, or before constructing raw commands."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_capabilities() -> str:
    ok, caps = _rpc("capabilities")
    return _text(caps) if ok else caps


@mcp.tool(
    name="formcut_extensions_list",
    description=(
        "List the extensions formcut has loaded (installed from FormPortal or run from a folder by form.ext): each one's id, "
        "name, version, source, state (ready, needs-permission or refused with the reason) and the commands it contributes. "
        "Use it before formcut_extension_command to find the id and command."
    ),
    annotations={"readOnlyHint": True, "openWorldHint": False},
)
def formcut_extensions_list() -> str:
    ok, result = _rpc("extensions.list", timeout=30)
    if not ok:
        return result
    rows = result.get("extensions", [])
    if not rows:
        return "formcut has no extensions. Install one in FormPortal, or run one from a folder with form.ext."
    lines = [] if result.get("window") else [f"Note: {result.get('note', 'the formcut window is not open')}."]
    for row in rows:
        state = row.get("state", "?") + (f" ({row['reason']})" if row.get("reason") else "")
        lines.append(f"{row['id']}  {row.get('name', '')} {row.get('version', '')}  {row.get('source', '')}  {state}")
        lines += [f"    command {c['id']}: {c['title']}" for c in row.get("commands", [])]
    return "\n".join(lines)


@mcp.tool(
    name="formcut_extension_command",
    description=(
        "Run a command an extension contributes, in the open formcut window, as if the person chose it from the Extensions "
        "menu. The first run of an extension version asks the person in the window to allow its permissions, so the call "
        "can wait for them; Not Now fails the call. Take the id and command from formcut_extensions_list."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": False},
)
def formcut_extension_command(
    id: Annotated[str, Field(description="The extension id, from formcut_extensions_list")],
    command: Annotated[str, Field(description="The command id, from formcut_extensions_list")],
    args: Annotated[dict | None, Field(description="Arguments for the command, if it takes any")] = None,
) -> str:
    ok, result = _rpc("extensions.command", {"id": id, "command": command, "args": args or {}}, timeout=180)
    if not ok:
        return result
    value = result.get("result")
    return f"Ran {id}: {command}." + ("" if value is None else f" Result: {_text(value)}")


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
