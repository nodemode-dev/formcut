"""Timeline interchange: OpenTimelineIO (.otio JSON) and CMX 3600 EDL, both ways.

After FilmCraft's interchange crate (github.com/storytold/filmcraft, MIT OR Apache-2.0, studied, not copied): an
importer returns a timeline plus a report of everything it could not carry; an exporter never fails on what a format
cannot hold, it reports it. formcut's own clip and track state rides in metadata.formcut, so a round trip through OTIO
gives back exactly what went out. OTIO's stack runs bottom to top; formcut's tracks run top first.
"""

import math
import re
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from .media import MEDIA_DIR, list_media

router = APIRouter(prefix="/api/interchange")


# ----------------------------------------------------------------------------------------------- time


def _rt(seconds: float, rate: float) -> dict:
    return {"OTIO_SCHEMA": "RationalTime.1", "rate": float(rate), "value": round(seconds * rate, 6)}


def _range(start: float, duration: float, rate: float) -> dict:
    return {"OTIO_SCHEMA": "TimeRange.1", "start_time": _rt(start, rate), "duration": _rt(duration, rate)}


def _seconds(rt: dict | None) -> float:
    if not rt:
        return 0.0
    rate = float(rt.get("rate") or 1.0)
    return float(rt.get("value") or 0.0) / rate


def _timecode(seconds: float, fps: float) -> str:
    """Non-drop timecode at the nearest whole rate."""
    base = max(1, round(fps))
    frames = round(seconds * base)
    return f"{frames // (3600 * base):02d}:{frames // (60 * base) % 60:02d}:{frames // base % 60:02d}:{frames % base:02d}"


def _frames(code: str, fps: float, drop: bool) -> int:
    """A timecode's frame count; drop-frame (29.97, 59.94) skips the first frame numbers of each minute but every tenth."""
    hours, minutes, seconds, frames = (int(x) for x in re.split("[:;.]", code))
    base = max(1, round(fps))
    total = ((hours * 60 + minutes) * 60 + seconds) * base + frames
    if drop:
        dropped = 2 if base == 30 else 4
        total_minutes = hours * 60 + minutes
        total -= dropped * (total_minutes - total_minutes // 10)
    return total


# ----------------------------------------------------------------------------------------------- media


def _media_file(media_id: str) -> str | None:
    found = sorted(MEDIA_DIR.glob(f"{media_id}.*"))
    return str(found[0]) if found else None


def _match(name: str, url: str, media: list[dict]) -> dict | None:
    """A library item for a clip from elsewhere: by formcut's id in the path, else by file name."""
    for item in media:
        if item["id"] and item["id"] in (url or ""):
            return item
    wanted = {(name or "").lower(), (url or "").replace("\\", "/").rsplit("/", 1)[-1].lower()}
    for item in media:
        if item["name"].lower() in wanted:
            return item
    return None


# ----------------------------------------------------------------------------------------------- OTIO


def export_otio(project: dict, timeline_index: int | None = None) -> tuple[dict, list[str]]:
    fps = float(project.get("fps") or 30)
    index = project.get("activeTimeline", 0) if timeline_index is None else timeline_index
    timeline = project["timelines"][index]
    report: list[str] = []
    children = []
    for track_index, track in reversed(list(enumerate(timeline["tracks"]))):
        clips = sorted(track.get("clips", []), key=lambda c: c["start"])
        kind = "Audio" if clips and all(c.get("kind") == "audio" for c in clips) else "Video"
        items, position = [], 0.0
        for clip in clips:
            if clip["start"] > position + 1e-6:
                items.append(
                    {
                        "OTIO_SCHEMA": "Gap.1",
                        "name": "",
                        "source_range": _range(0, clip["start"] - position, fps),
                        "effects": [],
                        "markers": [],
                        "metadata": {},
                    }
                )
            elif clip["start"] < position - 1e-6:
                report.append(
                    f"{track.get('name', track_index)}: {clip.get('label', clip['id'])} overlaps the clip before it and starts where that ends"
                )
            items.append(_otio_clip(clip, fps, report))
            position = max(position, clip["start"]) + clip["duration"]
        children.append(
            {
                "OTIO_SCHEMA": "Track.1",
                "name": track.get("name", ""),
                "kind": kind,
                "children": items,
                "effects": [],
                "markers": [],
                "enabled": not track.get("hidden", False),
                "metadata": {"formcut": {"track": {k: v for k, v in track.items() if k != "clips"}}},
            }
        )
    document = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": timeline.get("name") or project.get("title", "formcut"),
        "global_start_time": None,
        "tracks": {
            "OTIO_SCHEMA": "Stack.1",
            "name": "tracks",
            "children": children,
            "effects": [],
            "markers": [],
            "enabled": True,
            "metadata": {},
        },
        "metadata": {"formcut": {"fps": fps, "width": project.get("width"), "height": project.get("height")}},
    }
    return document, report


def _otio_clip(clip: dict, fps: float, report: list[str]) -> dict:
    name = clip.get("label") or clip.get("kind", "clip")
    path = _media_file(clip["mediaId"]) if clip.get("mediaId") else None
    if path:
        reference = {
            "OTIO_SCHEMA": "ExternalReference.1",
            "name": name,
            "target_url": f"file://{path}",
            "available_range": None,
            "metadata": {},
        }
    else:
        reference = {"OTIO_SCHEMA": "MissingReference.1", "name": name, "available_range": None, "metadata": {}}
        report.append(f"{name}: a {clip.get('kind', 'clip')} clip has no media file; it travels as metadata only")
    effects = []
    speed = float(clip.get("speed") or 1.0)
    if abs(speed - 1.0) > 1e-6:
        effects.append(
            {"OTIO_SCHEMA": "LinearTimeWarp.1", "name": "", "effect_name": "LinearTimeWarp", "time_scalar": speed, "metadata": {}}
        )
    return {
        "OTIO_SCHEMA": "Clip.1",
        "name": name,
        "source_range": _range(float(clip.get("sourceIn") or 0.0), clip["duration"], fps),
        "media_reference": reference,
        "effects": effects,
        "markers": [],
        "enabled": True,
        "metadata": {"formcut": {"clip": clip}},
    }


def import_otio(document: dict, media: list[dict]) -> tuple[dict, list[str]]:
    report: list[str] = []
    timeline = document
    if timeline.get("OTIO_SCHEMA", "").startswith("SerializableCollection"):
        timeline = next((c for c in timeline.get("children", []) if c.get("OTIO_SCHEMA", "").startswith("Timeline")), None) or {}
    if not timeline.get("OTIO_SCHEMA", "").startswith("Timeline"):
        raise ValueError("No OpenTimelineIO timeline in this file")
    stack = timeline.get("tracks") or {}
    tracks = []
    for track in reversed(stack.get("children", [])):
        if not track.get("OTIO_SCHEMA", "").startswith("Track"):
            report.append(f"{track.get('name', 'an item')}: a {track.get('OTIO_SCHEMA')} in the stack is not a track; left out")
            continue
        saved = ((track.get("metadata") or {}).get("formcut") or {}).get("track") or {}
        out = {**saved, "id": str(uuid.uuid4()), "name": track.get("name") or saved.get("name") or track.get("kind", "Track"), "clips": []}
        position = 0.0
        for item in track.get("children", []):
            schema = item.get("OTIO_SCHEMA", "")
            source = item.get("source_range") or {}
            duration = _seconds(source.get("duration"))
            if schema.startswith("Gap"):
                position += duration
            elif schema.startswith("Transition"):
                report.append(f"{out['name']}: a transition ({item.get('transition_type', 'dissolve')}) is not carried; the cut stays")
            elif schema.startswith("Clip"):
                clip = _otio_import_clip(item, position, duration, media, report, out["name"])
                if clip:
                    out["clips"].append(clip)
                position += duration
            else:
                report.append(f"{out['name']}: a {schema or 'nested item'} is not carried; its time is kept as a gap")
                position += duration
        tracks.append(out)
    return {"id": str(uuid.uuid4()), "name": timeline.get("name") or "Imported", "tracks": tracks}, report


def _otio_import_clip(item: dict, position: float, duration: float, media: list[dict], report: list[str], track: str) -> dict | None:
    saved = ((item.get("metadata") or {}).get("formcut") or {}).get("clip")
    reference = item.get("media_reference") or {}
    if not reference and item.get("media_references"):
        reference = item["media_references"].get(item.get("active_media_reference_key", "DEFAULT_MEDIA")) or {}
    source_in = _seconds((item.get("source_range") or {}).get("start_time")) - _seconds(
        (reference.get("available_range") or {}).get("start_time")
    )
    if saved and (not saved.get("mediaId") or any(m["id"] == saved["mediaId"] for m in media)):
        return {**saved, "id": str(uuid.uuid4()), "start": round(position, 6), "duration": round(duration, 6)}
    found = _match(item.get("name", ""), reference.get("target_url", ""), media)
    if not found:
        report.append(f"{track}: {item.get('name') or 'a clip'} is not in the media library; import its file and import the timeline again")
        return None
    clip = {
        "id": str(uuid.uuid4()),
        "kind": found["kind"],
        "label": found["name"],
        "start": round(position, 6),
        "duration": round(duration, 6),
        "mediaId": found["id"],
        "sourceIn": round(max(0.0, source_in), 6),
    }
    if found["kind"] == "video":
        clip["filmstrip"] = True
    for effect in item.get("effects") or []:
        if effect.get("OTIO_SCHEMA", "").startswith("LinearTimeWarp"):
            clip["speed"] = float(effect.get("time_scalar") or 1.0)
        else:
            report.append(
                f"{track}: {item.get('name')}: the effect {effect.get('effect_name') or effect.get('OTIO_SCHEMA')} is not carried"
            )
    return clip


# ----------------------------------------------------------------------------------------------- EDL

EVENT = re.compile(
    r"^\s*(\d{3,6})\s+(\S+)\s+(\S+)\s+(C|D|W\d+|K\s*B?|K\s*O)\s+(\d+\s+)?"
    r"(\d\d[:;]\d\d[:;]\d\d[:;.]\d\d)\s+(\d\d[:;]\d\d[:;]\d\d[:;.]\d\d)\s+(\d\d[:;]\d\d[:;]\d\d[:;.]\d\d)\s+(\d\d[:;]\d\d[:;]\d\d[:;.]\d\d)"
)
RECORD_START = 3600.0  # 01:00:00:00, where a CMX record starts by convention


def export_edl(project: dict, track_index: int, timeline_index: int | None = None) -> tuple[str, list[str]]:
    fps = float(project.get("fps") or 30)
    index = project.get("activeTimeline", 0) if timeline_index is None else timeline_index
    track = project["timelines"][index]["tracks"][track_index]
    report: list[str] = []
    if abs(fps - round(fps)) > 1e-3:
        report.append(f"{fps:g} fps is written as {round(fps)} fps non-drop timecode")
    lines = [f"TITLE: {(project.get('title') or 'formcut')[:70]}", "FCM: NON-DROP FRAME", ""]
    event = 0
    for clip in sorted(track.get("clips", []), key=lambda c: c["start"]):
        name = clip.get("label") or clip.get("kind", "clip")
        if not clip.get("mediaId"):
            report.append(f"{name}: a {clip.get('kind', 'clip')} clip has no source and cannot be an EDL event")
            continue
        event += 1
        channel = "A" if clip.get("kind") == "audio" else "V"
        source_in = float(clip.get("sourceIn") or 0.0)
        speed = float(clip.get("speed") or 1.0)
        source_out = source_in + clip["duration"] * speed
        record_in = RECORD_START + clip["start"]
        record_out = record_in + clip["duration"]
        lines.append(
            f"{event:03d}  AX       {channel:<5} C        {_timecode(source_in, fps)} {_timecode(source_out, fps)} {_timecode(record_in, fps)} {_timecode(record_out, fps)}"
        )
        if abs(speed - 1.0) > 1e-6:
            lines.append(f"M2   AX       {fps * speed:05.1f}                {_timecode(source_in, fps)}")
        lines.append(f"* FROM CLIP NAME: {name}")
        path = _media_file(clip["mediaId"])
        if path:
            lines.append(f"* SOURCE FILE: {path}")
        lines.append("")
    return "\n".join(lines) + "\n", report


def import_edl(text: str, media: list[dict], fps: float) -> tuple[dict, list[str]]:
    report: list[str] = []
    drop = bool(re.search(r"^FCM:\s*DROP FRAME", text, re.MULTILINE))
    events: list[dict] = []
    for line in text.splitlines():
        hit = EVENT.match(line)
        if hit:
            reel, channel, transition = hit.group(2), hit.group(3).upper(), hit.group(4).strip()
            codes = [_frames(hit.group(i), fps, drop) for i in (6, 7, 8, 9)]
            events.append({"reel": reel, "channel": channel, "transition": transition, "codes": codes, "name": reel})
            if transition != "C":
                report.append(f"event {hit.group(1)}: a {transition} transition is not carried; it comes in as a cut")
            continue
        comment = re.match(r"^\*\s*FROM CLIP NAME:\s*(.+)$", line.strip())
        if comment and events:
            events[-1]["name"] = comment.group(1).strip()
    if not events:
        raise ValueError("No CMX 3600 events in this file")
    base = max(1, round(fps))
    origin = min(e["codes"][2] for e in events)
    lanes: dict[str, dict] = {}
    for e in events:
        lane = "V" if e["channel"].startswith("V") or e["channel"] == "B" else "A"
        track = lanes.setdefault(lane, {"id": str(uuid.uuid4()), "name": "V1" if lane == "V" else "A1", "clips": []})
        found = _match(e["name"], "", media) or _match(e["reel"], "", media)
        if not found:
            report.append(f"{e['name']}: not in the media library; import its file and import the EDL again")
            continue
        source_in, source_out, record_in, record_out = e["codes"]
        clip = {
            "id": str(uuid.uuid4()),
            "kind": found["kind"],
            "label": found["name"],
            "start": round((record_in - origin) / base, 6),
            "duration": round(max(1, record_out - record_in) / base, 6),
            "mediaId": found["id"],
            "sourceIn": round(source_in / base, 6),
        }
        if found["kind"] == "video":
            clip["filmstrip"] = True
        if source_out - source_in != record_out - record_in and record_out > record_in:
            clip["speed"] = round((source_out - source_in) / (record_out - record_in), 6)
        track["clips"].append(clip)
    tracks = [lanes[k] for k in ("V", "A") if k in lanes]
    return {"id": str(uuid.uuid4()), "name": "Imported EDL", "tracks": tracks}, report


# ----------------------------------------------------------------------------------------------- routes


class ExportBody(BaseModel):
    project: dict
    timeline: int | None = None
    track: int = 0


class ImportBody(BaseModel):
    text: str
    fps: float = 30.0


@router.post("/export/{fmt}")
def export_route(fmt: str, body: ExportBody) -> Response:
    """The timeline as an OpenTimelineIO or EDL file; the report travels in the X-Formcut-Report header (JSON)."""
    import json

    if fmt == "otio":
        document, report = export_otio(body.project, body.timeline)
        data, media_type, suffix = json.dumps(document, indent=2), "application/json", "otio"
    elif fmt == "edl":
        data, report = export_edl(body.project, body.track, body.timeline)
        media_type, suffix = "text/plain", "edl"
    else:
        raise HTTPException(404, f"No exporter for {fmt}")
    title = re.sub(r"[^A-Za-z0-9_-]+", "_", body.project.get("title") or "formcut").strip("_") or "formcut"
    headers = {"Content-Disposition": f'attachment; filename="{title}.{suffix}"', "X-Formcut-Report": json.dumps(report)[:6000]}
    return Response(data, media_type=media_type, headers=headers)


@router.post("/import/{fmt}")
def import_route(fmt: str, body: ImportBody) -> dict:
    """A timeline from an OpenTimelineIO or EDL file, its media matched in the library, and the report."""
    import json

    media = list_media()
    try:
        if fmt == "otio":
            timeline, report = import_otio(json.loads(body.text), media)
        elif fmt == "edl":
            timeline, report = import_edl(body.text, media, body.fps if math.isfinite(body.fps) and body.fps > 0 else 30.0)
        else:
            raise HTTPException(404, f"No importer for {fmt}")
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, f"Could not read this {fmt.upper()} file: {exc}") from None
    return {"timeline": timeline, "report": report}
