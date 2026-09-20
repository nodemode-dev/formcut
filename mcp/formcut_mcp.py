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

Built against mcp 2.2.0, where the server class is MCPServer (renamed from
FastMCP in the 2.x line). Transport is stdio, which is what a desktop host
launches.
"""

from __future__ import annotations

import json
import os
from typing import Annotated, Any

import httpx
from mcp.server.mcpserver import MCPServer
from pydantic import Field

ENGINE = os.environ.get("FORMCUT_ENGINE", "http://127.0.0.1:8040").rstrip("/")
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
            f"The formcut engine is not answering at {ENGINE}. Start it with ./formcut in the "
            "repository, or set FORMCUT_ENGINE if it listens elsewhere."
        )
    if isinstance(error, httpx.TimeoutException):
        return (
            f"The engine at {ENGINE} did not answer within {TIMEOUT:.0f} s. A long render is "
            "normal: submit with formcut_render and poll formcut_render_status instead of waiting."
        )
    return f"Could not reach the engine at {ENGINE}: {error.__class__.__name__}: {error}"


def _rest(method: str, path: str, payload: dict | None = None) -> tuple[bool, Any]:
    try:
        with httpx.Client(timeout=TIMEOUT, headers=HEADERS) as client:
            response = client.request(method, f"{ENGINE}{path}", json=payload)
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


def _rpc(method: str, params: dict | None = None, identify: bool = True) -> tuple[bool, Any]:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": 1, "method": method}
    params = dict(params or {})
    if identify:
        session = _session_id()
        if session:
            params["session"] = session
    if params:
        body["params"] = params
    try:
        with httpx.Client(timeout=TIMEOUT, headers=HEADERS) as client:
            response = client.post(f"{ENGINE}/api/rpc", json=body)
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
        f"engine {health.get('status', 'unknown')}, version {health.get('version', 'unknown')} at {ENGINE}",
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
                for clip in track.get("clips", [])
            )
            or "empty"
        )
        lines.append(f"track {index} ({track.get('name', 'track')}): {clips}")
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
        "path. Format is mp4 or webm; quality is low, medium or high."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
)
def formcut_render(
    project_id: Annotated[str, Field(description="Project id to render")],
    file_format: Annotated[str, Field(description="Output container: mp4 or webm")] = "mp4",
    quality: Annotated[str, Field(description="Encoder ladder: low, medium or high")] = "high",
) -> str:
    if file_format not in ("mp4", "webm"):
        return "format must be mp4 or webm"
    if quality not in ("low", "medium", "high"):
        return "quality must be low, medium or high"
    ok, job = _rpc("project.export", {"id": project_id, "format": file_format, "quality": quality})
    if not ok:
        return job
    job_id = job.get("job_id")
    return (
        f"render started as job {job_id} ({file_format}, {quality})\n"
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
            f"render done\nfile: {state.get('file')}\nname: {state.get('name')}\n"
            f"type: {state.get('media_type')}\nalso fetchable from {ENGINE}{state.get('url')}"
        )
    status = state.get("status", "unknown")
    if status in ("cancelled", "error"):
        return f"render {status}. Start a new one with formcut_render when the cause is fixed."
    percent = round(float(state.get("progress") or 0) * 100)
    return f"render {status}, {percent}% done. Poll again shortly."


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


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
