import copy
import itertools
import shutil
import tempfile
import threading
import uuid
from pathlib import Path

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
        tail.update(
            id=uuid.uuid4().hex,
            start=clip["start"] + offset,
            duration=clip["duration"] - offset,
            sourceIn=source_time(clip, offset),
            fadeIn=0,
        )
        tail.pop("transitionIn", None)
        if clip.get("speedCurve"):
            tail["speedCurve"] = [{"t": 0, "speed": speed_at(clip, offset)}] + [
                {"t": p["t"] - offset, "speed": p["speed"]} for p in clip["speedCurve"] if p["t"] > offset
            ]
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
    elif operation == "clips.split":
        tracks = timeline["tracks"]
        at = float(command["time"])
        made = []
        for wanted in command["clipIds"]:
            spot = next(((t, c) for t in tracks if not t.get("locked") for c in t["clips"] if c["id"] == wanted), None)
            if not spot:
                continue
            track, clip = spot
            offset = at - clip["start"]
            if not 0.1 <= offset <= clip["duration"] - 0.1:
                continue
            tail = copy.deepcopy(clip)
            tail.update(
                id=uuid.uuid4().hex,
                start=clip["start"] + offset,
                duration=clip["duration"] - offset,
                sourceIn=source_time(clip, offset),
                fadeIn=0,
            )
            tail.pop("transitionIn", None)
            if clip.get("speedCurve"):
                tail["speedCurve"] = [{"t": 0, "speed": speed_at(clip, offset)}] + [
                    {"t": p["t"] - offset, "speed": p["speed"]} for p in clip["speedCurve"] if p["t"] > offset
                ]
            tail["keyframes"] = [{**k, "t": k["t"] - offset} for k in clip.get("keyframes", [])]
            clip["duration"] = offset
            clip["fadeOut"] = 0
            track["clips"].append(tail)
            made.append(tail["id"])
        return {"clipIds": made}
    elif operation == "clip.rejoin":
        tracks = timeline["tracks"]
        wanted = list(command["clipIds"])
        if len(wanted) < 2:
            raise ValueError("Select two or more pieces to rejoin")
        spots = []
        for cid in wanted:
            spot = next(((i, t, c) for i, t in enumerate(tracks) for c in t["clips"] if c["id"] == cid), None)
            if not spot:
                raise ValueError("Clip not found")
            spots.append(spot)
        track_index = spots[0][0]
        if any(s[0] != track_index for s in spots):
            raise ValueError("Pieces must sit on one track")
        if tracks[track_index].get("locked"):
            raise ValueError("The track is locked")
        ordered = sorted((s[2] for s in spots), key=lambda c: c["start"])
        media = ordered[0].get("mediaId")
        if any(c.get("mediaId") != media for c in ordered):
            raise ValueError("Pieces must share the same media")
        speed = ordered[0].get("speed", 1)
        if any(c.get("speedCurve") or c.get("speed", 1) != speed for c in ordered):
            raise ValueError("Pieces must play at the same constant speed")
        for prev, nxt in itertools.pairwise(ordered):
            if abs(prev["start"] + prev["duration"] - nxt["start"]) > 0.02:
                raise ValueError("Pieces must touch on the timeline")
            if abs(source_time(prev, prev["duration"]) - nxt.get("sourceIn", 0)) > 0.02:
                raise ValueError("Pieces must continue the same source range")
        first, last = ordered[0], ordered[-1]
        at = first["duration"]
        merged = list(first.get("keyframes") or [])
        for piece in ordered[1:]:
            merged.extend({**copy.deepcopy(k), "t": k["t"] + at} for k in piece.get("keyframes") or [])
            at += piece["duration"]
        first["duration"] = round((last["start"] + last["duration"] - first["start"]) * 100) / 100
        if merged:
            first["keyframes"] = sorted(merged, key=lambda k: k["t"])
        else:
            first.pop("keyframes", None)
        first["fadeOut"] = last.get("fadeOut", 0)
        gone = {c["id"] for c in ordered[1:]}
        tracks[track_index]["clips"] = [c for c in tracks[track_index]["clips"] if c["id"] not in gone]
    elif operation == "clip.freeze-insert":
        if not located:
            raise ValueError("Clip not found")
        track, clip = located
        hold = max(0.1, float(command.get("hold", 3)))
        at = float(command["time"])
        offset = at - clip["start"]
        if not 0.1 <= offset <= clip["duration"] - 0.1:
            raise ValueError("Place the time inside the clip")
        tail = copy.deepcopy(clip)
        tail.update(
            id=uuid.uuid4().hex,
            start=clip["start"] + offset + hold,
            duration=clip["duration"] - offset,
            sourceIn=source_time(clip, offset),
            fadeIn=0,
        )
        tail.pop("transitionIn", None)
        if clip.get("speedCurve"):
            tail["speedCurve"] = [{"t": 0, "speed": speed_at(clip, offset)}] + [
                {"t": p["t"] - offset, "speed": p["speed"]} for p in clip["speedCurve"] if p["t"] > offset
            ]
        tail["keyframes"] = [{**k, "t": k["t"] - offset} for k in clip.get("keyframes", [])]
        clip["duration"] = offset
        clip["fadeOut"] = 0
        cut = clip["start"] + clip["duration"]
        for other in track["clips"]:
            if other is not clip and other["start"] >= cut - 0.005:
                other["start"] = round((other["start"] + hold) * 100) / 100
        still = {
            "id": uuid.uuid4().hex,
            "kind": "image",
            "label": str(command.get("label", "Freeze frame")),
            "mediaId": str(command["mediaId"]),
            "start": cut,
            "duration": hold,
        }
        if clip.get("transform"):
            still["transform"] = copy.deepcopy(clip["transform"])
        track["clips"].extend([still, tail])
        return {"stillId": still["id"], "tailId": tail["id"]}
    elif operation == "clip.detach":
        if not located:
            raise ValueError("Clip not found")
        _, clip = located
        audio = copy.deepcopy(clip)
        audio.update(
            id=uuid.uuid4().hex,
            kind="audio",
            mediaId=str(command["mediaId"]),
            label=str(command.get("label", clip.get("label", "Audio"))),
            muted=False,
            detachedFrom=clip["id"],
        )
        for key in ("effects", "effectId", "cutout", "shaderId", "lutId", "colour", "crop"):
            audio.pop(key, None)
        target = next((t for t in timeline["tracks"] if "audio" in str(t.get("name", "")).lower() and not t.get("locked")), None)
        if target is None:
            target = {"id": uuid.uuid4().hex, "name": "Audio", "clips": []}
            timeline["tracks"].append(target)
        target["clips"].append(audio)
        clip["muted"] = True
        return {"audioId": audio["id"]}
    elif operation == "clip.ripple-delete":
        if not located:
            raise ValueError("Clip not found")
        track, clip = located
        span = clip["duration"]
        at = clip["start"]
        track["clips"].remove(clip)
        for other in track["clips"]:
            if other["start"] >= at:
                other["start"] = round(max(0.0, other["start"] - span) * 100) / 100
    elif operation == "timeline.cut-range":
        # Text-based editing over RPC: a span leaves every track, clips inside
        # it go, clips straddling it are cut into a head and a tail, and what
        # follows moves back by the length, the interface's own command.
        start = min(float(command["start"]), float(command["end"]))
        length = abs(float(command["end"]) - float(command["start"]))
        if length <= 0.01:
            raise ValueError("A cut range needs a length")
        end = start + length
        for track in timeline["tracks"]:
            kept = []
            for clip in track["clips"]:
                clip_end = clip["start"] + clip["duration"]
                if clip_end <= start + 1e-6:
                    kept.append(clip)
                elif clip["start"] >= end - 1e-6:
                    clip["start"] = round((clip["start"] - length) * 1000) / 1000
                    kept.append(clip)
                elif clip["start"] >= start - 1e-6 and clip_end <= end + 1e-6:
                    continue
                elif clip["start"] < start and clip_end > end:
                    tail = {
                        **clip,
                        "id": uuid.uuid4().hex,
                        "start": start,
                        "duration": max(0.05, clip_end - end),
                        "sourceIn": clip.get("sourceIn", 0) + (end - clip["start"]),
                    }
                    clip["duration"] = max(0.05, start - clip["start"])
                    kept += [clip, tail]
                elif clip["start"] < start:
                    clip["duration"] = max(0.05, start - clip["start"])
                    kept.append(clip)
                else:
                    clip["sourceIn"] = clip.get("sourceIn", 0) + (end - clip["start"])
                    clip["duration"] = max(0.05, clip_end - end)
                    clip["start"] = start
                    kept.append(clip)
            track["clips"] = kept
    elif operation == "clip.speed-curve":
        if not located:
            raise ValueError("Clip not found")
        _, clip = located
        points = command.get("points")
        if points is None:
            clip.pop("speedCurve", None)
        else:
            if not isinstance(points, list) or not points:
                raise ValueError("A speed curve needs points")
            clip["speedCurve"] = [{"t": float(p["t"]), "speed": float(p["speed"])} for p in points]
    elif operation == "clip.animations":
        if not located:
            raise ValueError("Clip not found")
        _, clip = located
        slots = command.get("animations")
        if slots is None:
            clip.pop("animations", None)
        else:
            clip["animations"] = slots
    elif operation == "clip.reattach":
        if not located:
            raise ValueError("Clip not found")
        _, picked = located
        every = [(t, c) for t in timeline["tracks"] for c in t["clips"]]
        if picked.get("detachedFrom"):
            audio_spot = next(((t, c) for t, c in every if c is picked), None)
            video_spot = next(((t, c) for t, c in every if c["id"] == picked["detachedFrom"]), None)
        else:
            video_spot = next(((t, c) for t, c in every if c is picked), None)
            audio_spot = next(((t, c) for t, c in every if c.get("detachedFrom") == picked["id"]), None)
        if not audio_spot or not video_spot:
            raise ValueError("No detached sound belongs to this clip")
        audio_spot[0]["clips"].remove(audio_spot[1])
        video_spot[1].pop("muted", None)
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
    elif operation == "marker.add":
        markers = timeline.setdefault("markers", [])
        if len(markers) >= 512:
            raise ValueError("Marker limit reached")
        marker = {"id": uuid.uuid4().hex, "t": round(max(0.0, float(command.get("t") or 0)), 3)}
        if isinstance(command.get("colour"), str):
            marker["colour"] = command["colour"][:16]
        if isinstance(command.get("note"), str):
            marker["note"] = command["note"][:400]
        markers.append(marker)
        markers.sort(key=lambda entry: entry["t"])
    elif operation == "marker.remove":
        timeline["markers"] = [entry for entry in timeline.get("markers", []) if entry.get("id") != command.get("id")]
    elif operation == "marker.update":
        marker = next((entry for entry in timeline.get("markers", []) if entry.get("id") == command.get("id")), None)
        if marker is None:
            raise ValueError("No such marker")
        if command.get("t") is not None:
            marker["t"] = round(max(0.0, float(command["t"])), 3)
        if isinstance(command.get("colour"), str):
            marker["colour"] = command["colour"][:16]
        if isinstance(command.get("note"), str):
            marker["note"] = command["note"][:400]
        timeline["markers"].sort(key=lambda entry: entry["t"])
    elif operation == "track.remove":
        if len(timeline["tracks"]) < 2:
            raise ValueError("Keep at least one track")
        timeline["tracks"].pop(track_index)
    elif operation == "timeline.add":
        project["timelines"].append(
            {
                "id": uuid.uuid4().hex,
                "name": command.get("name", "Timeline"),
                "tracks": [{"id": uuid.uuid4().hex, "name": "Video", "clips": []}],
            }
        )
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
    if method == "captions.import":
        from .subtitles import parse

        cues = parse(str(params.get("text") or ""))
        if not cues:
            raise ValueError("No cues found: expected SRT or WebVTT text")
        return {"cues": [cue.model_dump() for cue in cues]}
    if method == "captions.export":
        from .subtitles import Cue, write

        fmt = "vtt" if params.get("format") == "vtt" else "srt"
        with _lock:
            project = store.get_project(str(params.get("id") or ""))
        if not project:
            raise ValueError("Project not found")
        tracks = project["timelines"][project.get("activeTimeline", 0)]["tracks"]
        track = int(params.get("track") or 0)
        if not 0 <= track < len(tracks):
            raise ValueError("No such track")
        clips = [c for c in tracks[track]["clips"] if c.get("kind") == "text"]
        cues = [
            Cue(start=c["start"], end=c["start"] + c["duration"], text=c.get("textStyle", {}).get("content", ""))
            for c in clips
            if c.get("textStyle", {}).get("content")
        ]
        if not cues:
            raise ValueError("No captions on that track")
        return {"format": fmt, "text": write(cues, fmt), "count": len(cues)}
    if method == "media.beats":
        from .media import _samples
        from .rhythm import beats

        return beats(_samples(str(params.get("id") or "")), 48000, float(params.get("sensitivity") or 0.5))
    if method == "media.ducking":
        from .media import _samples
        from .rhythm import ducking

        return ducking(_samples(str(params.get("id") or "")), 48000, depth=float(params.get("depth") or 0.25))
    if method == "media.scenes":
        from . import scenes as scene_module
        from .media import MEDIA_DIR, _find

        media_id = str(params.get("id") or "")
        _find(media_id)
        matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
        if not matches:
            raise ValueError("Media file is missing")
        return scene_module.scenes(matches[0], float(params.get("sensitivity") or 0.5))
    if method == "media.proxy":
        from . import proxies as proxy_module
        from .media import MEDIA_DIR, _find

        media_id = str(params.get("id") or "")
        _find(media_id)
        matches = list(MEDIA_DIR.glob(f"{media_id}.*"))
        source = matches[0] if matches else None
        action = str(params.get("action") or "status")
        if action == "build":
            if not source:
                raise ValueError("Media file is missing")
            return proxy_module.enqueue(media_id, source, int(params.get("size") or proxy_module.DEFAULT_LONG_SIDE))
        if action == "delete":
            return {"removed": proxy_module.remove(media_id)}
        return proxy_module.status(media_id, source)
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
        return {
            "ready": True,
            "status": "done",
            "file": result.get("file"),
            "name": result.get("name"),
            "media_type": result.get("media_type"),
            "url": f"/api/jobs/{job_id}/file",
        }
    if method == "capabilities":
        return {
            "methods": [
                "capabilities",
                "catalogue",
                "session.hello",
                "media.list",
                "media.import",
                "media.proxy",
                "media.scenes",
                "media.beats",
                "media.ducking",
                "captions.import",
                "captions.export",
                "project.list",
                "project.create",
                "project.get",
                "project.edit",
                "project.undo",
                "project.redo",
                "project.export",
                "job.result",
                "job.status",
                "job.cancel",
            ],
            "clip_properties": [
                "transform",
                "effects",
                "audioEffects",
                "speedCurve",
                "sourceIn",
                "keyframes",
                "expressions",
                "cutout",
                "lutId",
                "shaderId",
                "transitionIn",
                "textStyle",
                "volume",
                "pan",
                "muted",
                "reversed",
                "crop",
                "colour",
                "animations",
                "volumeKeys",
                "lutIntensity",
                "pitchFollowsSpeed",
                "audioStream",
                "angle",
                "audioAngle",
                "key",
                "mask",
                "fadeIn",
                "fadeOut",
                "label",
                "stabilise",
                "smoothSlow",
            ],
            "edit_commands": [
                "clip.add",
                "clip.remove",
                "clip.update",
                "clip.move",
                "clip.split",
                "clips.move",
                "clips.remove",
                "clips.duplicate",
                "clips.add",
                "clips.mute",
                "clips.split",
                "clip.rejoin",
                "clip.freeze-insert",
                "clip.reattach",
                "clip.detach",
                "clip.ripple-delete",
                "timeline.cut-range",
                "clip.speed-curve",
                "clip.animations",
                "clip.scenes",
                "track.add",
                "track.remove",
                "timeline.add",
                "project.settings",
                "project.background",
                "marker.add",
                "marker.remove",
                "marker.update",
            ],
        }
    if method == "catalogue":
        return catalogue()
    if method == "project.list":
        return store.list_projects()
    if method == "project.create":
        project = params.get("project") or {
            "title": params.get("title", "Untitled project"),
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "timelines": [
                {"id": uuid.uuid4().hex, "name": "Timeline 1", "tracks": [{"id": uuid.uuid4().hex, "name": "Video", "clips": []}]}
            ],
        }
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
            for timeline in project.get("timelines", []):
                for track in timeline.get("tracks", []):
                    if not track.get("magnetic"):
                        continue
                    track["clips"].sort(key=lambda c: c["start"])
                    cursor = 0.0
                    for spot in track["clips"]:
                        if spot["start"] != cursor:
                            spot["start"] = round(cursor * 100) / 100
                        cursor = spot["start"] + spot["duration"]
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
