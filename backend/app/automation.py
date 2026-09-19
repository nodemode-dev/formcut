import copy
import json
import shutil
import tempfile
from pathlib import Path
import threading
import uuid

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

from . import jobs, store
from .catalogue import catalogue
from .media import ingest_path, list_media
from .orchestration import SessionInput, note_operation, open_session
from .render_api import RenderInput, export
from .render_document import validate_document
from .timing import source_time, speed_at

router = APIRouter(prefix="/api/rpc", tags=["automation"])
_lock = threading.RLock()
_history = {}
_redo = {}


def apply_edit(project: dict, command: dict):
    operation = command["op"]
    timeline = project["timelines"][int(command.get("timeline", project.get("activeTimeline", 0)))]
    track_index = int(command.get("track", 0))
    located = next(((t, c) for t in timeline["tracks"] for c in t["clips"] if c["id"] == command.get("clipId")), None)
    if operation == "clip.add":
        clip = copy.deepcopy(command["clip"])
        clip.setdefault("id", uuid.uuid4().hex)
        timeline["tracks"][track_index]["clips"].append(clip)
    elif operation == "clip.remove":
        if not located:
            raise ValueError("Clip not found")
        located[0]["clips"].remove(located[1])
    elif operation == "clip.update":
        if not located:
            raise ValueError("Clip not found")
        patch = command["patch"]
        if "id" in patch:
            raise ValueError("Clip identity cannot be changed")
        located[1].update(copy.deepcopy(patch))
    elif operation == "clip.move":
        if not located:
            raise ValueError("Clip not found")
        located[0]["clips"].remove(located[1])
        located[1]["start"] = float(command["start"])
        timeline["tracks"][track_index]["clips"].append(located[1])
    elif operation == "clip.split":
        if not located:
            raise ValueError("Clip not found")
        clip = located[1]
        offset = float(command["time"]) - clip["start"]
        if not 0 < offset < clip["duration"]:
            raise ValueError("Split must be inside the clip")
        tail = copy.deepcopy(clip)
        tail.update(id=uuid.uuid4().hex, start=clip["start"] + offset, duration=clip["duration"] - offset, sourceIn=source_time(clip, offset), fadeIn=0)
        tail.pop("transitionIn", None)
        if clip.get("speedCurve"):
            tail["speedCurve"] = [{"t": 0, "speed": speed_at(clip, offset)}] + [{"t": p["t"] - offset, "speed": p["speed"]} for p in clip["speedCurve"] if p["t"] > offset]
        tail["keyframes"] = [{**k, "t": k["t"] - offset} for k in clip.get("keyframes", [])]
        clip["duration"] = offset
        clip["fadeOut"] = 0
        located[0]["clips"].append(tail)
    elif operation == "clips.move":
        tracks = timeline["tracks"]
        d_track = int(command.get("deltaTrack", 0))
        delta = float(command["deltaStart"])
        members = []
        for wanted in command["clipIds"]:
            spot = next(((i, t, c) for i, t in enumerate(tracks) for c in t["clips"] if c["id"] == wanted), None)
            if not spot:
                raise ValueError("Clip not found")
            members.append(spot)
        for index, track, clip in members:
            target = index + d_track
            if track.get("locked") or not 0 <= target < len(tracks) or tracks[target].get("locked") or clip["start"] + delta < 0:
                raise ValueError("Move lands on a locked track or before zero")
        for index, track, clip in members:
            if d_track:
                track["clips"].remove(clip)
                tracks[index + d_track]["clips"].append(clip)
            clip["start"] = max(0.0, round((clip["start"] + delta) * 100) / 100)
    elif operation == "clips.remove":
        tracks = timeline["tracks"]
        for wanted in command["clipIds"]:
            spot = next(((t, c) for t in tracks if not t.get("locked") for c in t["clips"] if c["id"] == wanted), None)
            if spot:
                spot[0]["clips"].remove(spot[1])
    elif operation == "clips.duplicate":
        tracks = timeline["tracks"]
        made = []
        for wanted in command["clipIds"]:
            spot = next(((t, c) for t in tracks if not t.get("locked") for c in t["clips"] if c["id"] == wanted), None)
            if not spot:
                continue
            twin = copy.deepcopy(spot[1])
            twin["id"] = uuid.uuid4().hex
            twin["start"] = spot[1]["start"] + spot[1]["duration"]
            spot[0]["clips"].append(twin)
            made.append(twin["id"])
        return {"clipIds": made}
    elif operation == "clips.add":
        tracks = timeline["tracks"]
        made = []
        for entry in command["entries"]:
            index = int(entry["track"])
            if not 0 <= index < len(tracks) or tracks[index].get("locked"):
                continue
            clip = copy.deepcopy(entry["clip"])
            clip.setdefault("id", uuid.uuid4().hex)
            tracks[index]["clips"].append(clip)
            made.append(clip["id"])
        return {"clipIds": made}
    elif operation == "clips.mute":
        tracks = timeline["tracks"]
        muted = bool(command["muted"])
        for wanted in command["clipIds"]:
            spot = next((c for t in tracks if not t.get("locked") for c in t["clips"] if c["id"] == wanted), None)
            if spot is not None:
                if muted:
                    spot["muted"] = True
                else:
                    spot.pop("muted", None)
    elif operation == "track.add":
        timeline["tracks"].append({"id": uuid.uuid4().hex, "name": command.get("name", "Track"), "clips": []})
    elif operation == "track.remove":
        if len(timeline["tracks"]) < 2:
            raise ValueError("Keep at least one track")
        timeline["tracks"].pop(track_index)
    elif operation == "timeline.add":
        project["timelines"].append({"id": uuid.uuid4().hex, "name": command.get("name", "Timeline"), "tracks": [{"id": uuid.uuid4().hex, "name": "Video", "clips": []}]})
    elif operation == "project.settings":
        allowed = {"title", "width", "height", "fps", "activeTimeline"}
        if set(command["patch"]) - allowed:
            raise ValueError("Unknown project setting")
        project.update(command["patch"])
    else:
        raise ValueError("Unknown editing command")


def dispatch(method: str, params: dict):
    # An orchestrator identifies itself once and then passes its session id with
    # each call, so the person in front of the app can see who is driving and
    # what they are doing. An anonymous caller still works; it is just unnamed.
    session_id = params.get("session") if isinstance(params, dict) else None
    if method != "capabilities":
        note_operation(session_id, method, {"project": params.get("id")} if isinstance(params, dict) and params.get("id") else None)
    if method == "session.hello":
        return open_session(SessionInput(name=str(params.get("name") or "orchestrator"), agent=params.get("agent")))
    if method == "media.list":
        return list_media()
    if method == "media.import":
        source = Path(str(params.get("path") or ""))
        if not source.is_file():
            raise ValueError("path does not name a readable file")
        # ingest_path moves what it is given, which is right for a temporary
        # render but destructive for a caller's own file: an orchestrator asking
        # the engine to import an asset must not lose it. Copy into a temporary
        # first, so the move consumes the copy.
        with tempfile.TemporaryDirectory() as folder:
            staged = Path(folder) / source.name
            shutil.copy2(source, staged)
            return ingest_path(staged, source.name, extra={"source": "orchestrator"})
    if method == "job.result":
        job_id = params.get("id") or params.get("job_id")
        if not job_id:
            raise ValueError("Supply a job id as id or job_id")
        state = jobs.status(str(job_id))
        if state.get("status") != "done":
            return {"ready": False, "status": state.get("status"), "progress": state.get("progress")}
        result = state.get("result") or {}
        return {"ready": True, "status": "done", "file": result.get("file"), "name": result.get("name"),
                "media_type": result.get("media_type"), "url": f"/api/jobs/{job_id}/file"}
    if method == "capabilities":
        return {"methods": ["capabilities", "catalogue", "session.hello", "media.list", "media.import", "project.list", "project.create", "project.get", "project.edit", "project.undo", "project.redo", "project.export", "job.result", "job.status", "job.cancel"], "clip_properties": ["transform", "effects", "audioEffects", "speedCurve", "sourceIn", "keyframes", "expressions", "cutout", "lutId", "shaderId", "transitionIn", "textStyle", "volume", "pan", "muted"], "edit_commands": ["clip.add", "clip.remove", "clip.update", "clip.move", "clip.split", "clips.move", "clips.remove", "clips.duplicate", "clips.add", "clips.mute", "track.add", "track.remove", "timeline.add", "project.settings"]}
    if method == "catalogue":
        return catalogue()
    if method == "project.list":
        return store.list_projects()
    if method == "project.create":
        project = params.get("project") or {"title": params.get("title", "Untitled project"), "width": 1920, "height": 1080, "fps": 30, "timelines": [{"id": uuid.uuid4().hex, "name": "Timeline 1", "tracks": [{"id": uuid.uuid4().hex, "name": "Video", "clips": []}]}]}
        project = validate_document(project)
        project.update(id=uuid.uuid4().hex, revision=1)
        return store.save_project(project)
    if method in ("job.status", "job.cancel"):
        job_id = params.get("id") or params.get("job_id")
        if not job_id:
            raise ValueError("Supply a job id as id or job_id")
        return jobs.status(job_id) if method == "job.status" else jobs.cancel(job_id)
    if method not in ("project.get", "project.export", "project.edit", "project.undo", "project.redo"):
        raise ValueError("Unknown API method")
    with _lock:
        project_id = params.get("id")
        if not project_id:
            raise ValueError("Supply a project id")
        project = store.get_project(project_id)
        if not project:
            raise ValueError("Project not found")
        if method == "project.get":
            return project
        if method == "project.export":
            return export(RenderInput(project=project, format=params.get("format", "mp4"), quality=params.get("quality", "high")))
        version = int(project.get("revision", 0))
        if "revision" in params and params["revision"] != version:
            raise ValueError("Project changed; read the current revision before editing")
        before = copy.deepcopy(project)
        if method == "project.edit":
            commands = params["commands"]
            if not isinstance(commands, list) or not 1 <= len(commands) <= 1000:
                raise ValueError("Supply between 1 and 1000 commands")
            for command in commands:
                apply_edit(project, command)
            project = validate_document(project)
            _history.setdefault(project_id, []).append(before)
            _history[project_id] = _history[project_id][-50:]
            _redo[project_id] = []
        elif method in ("project.undo", "project.redo"):
            source, target = (_history, _redo) if method == "project.undo" else (_redo, _history)
            if not source.get(project_id):
                raise ValueError("No history in this engine session")
            target.setdefault(project_id, []).append(before)
            project = source[project_id].pop()
        else:
            raise ValueError("Unknown API method")
        project["revision"] = version + 1
        return store.save_project(project, expected_revision=version)


def rpc(message):
    if isinstance(message, list):
        return [reply for item in message for reply in [rpc(item)] if reply is not None]
    request_id = message.get("id") if isinstance(message, dict) else None
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "Invalid JSON-RPC request"}}
    try:
        result = dispatch(message["method"], message.get("params") or {})
        return {"jsonrpc": "2.0", "id": request_id, "result": result} if "id" in message else None
    except (ValueError, KeyError, IndexError, TypeError, HTTPException) as exc:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": str(exc)}} if "id" in message else None


@router.post("")
async def http_rpc(request: Request):
    try:
        return rpc(await request.json())
    except (ValueError, UnicodeError):
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON"}}


@router.websocket("/ws")
async def websocket_rpc(socket: WebSocket):
    if socket.client and socket.client.host not in ("127.0.0.1", "::1", "testclient"):
        await socket.close(code=1008)
        return
    await socket.accept()
    try:
        while True:
            response = rpc(await socket.receive_json())
            if response is not None:
                await socket.send_json(response)
    except WebSocketDisconnect:
        return
