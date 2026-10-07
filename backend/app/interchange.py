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


def export_otio(project: dict, timeline_index: int | None = None, media: list[dict] | None = None) -> tuple[dict, list[str]]:
    fps = float(project.get("fps") or 30)
    durations = {item["id"]: float(item.get("duration") or 0.0) for item in media or []}
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
            items.append(_otio_clip(clip, fps, report, durations.get(clip.get("mediaId") or "", 0.0)))
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


def _otio_clip(clip: dict, fps: float, report: list[str], available: float = 0.0) -> dict:
    name = clip.get("label") or clip.get("kind", "clip")
    path = _media_file(clip["mediaId"]) if clip.get("mediaId") else None
    if path:
        # the file's extent: OTIO's FCP XML writer (and other tools) need it to place the clip in its source
        reference = {
            "OTIO_SCHEMA": "ExternalReference.1",
            "name": name,
            "target_url": f"file://{path}",
            "available_range": _range(0, available, fps) if available > 0 else None,
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


# ----------------------------------------------------------------------------------------------- FCP 7 XML


def _timebase(fps: float) -> tuple[int, bool]:
    """FCP 7 rates are a whole timebase plus an NTSC flag (29.97 is 30 with ntsc TRUE)."""
    return max(1, round(fps)), abs(fps - round(fps)) > 1e-3


def _xml_rate(parent, fps: float) -> None:
    from xml.etree.ElementTree import SubElement

    timebase, ntsc = _timebase(fps)
    rate = SubElement(parent, "rate")
    SubElement(rate, "timebase").text = str(timebase)
    SubElement(rate, "ntsc").text = "TRUE" if ntsc else "FALSE"


def export_fcp7(project: dict, media: list[dict], timeline_index: int | None = None) -> tuple[str, list[str]]:
    """xmeml 5, the dialect Premiere Pro imports and exports. V1 is the bottom track; each file is written once in full
    and then referenced by its id; paths are file://localhost URLs."""
    from urllib.parse import quote
    from xml.etree.ElementTree import Element, SubElement, tostring

    fps = float(project.get("fps") or 30)
    index = project.get("activeTimeline", 0) if timeline_index is None else timeline_index
    timeline = project["timelines"][index]
    report: list[str] = []
    library = {item["id"]: item for item in media}
    frames = lambda seconds: round(seconds * fps)  # noqa: E731
    end = max((c["start"] + c["duration"] for t in timeline["tracks"] for c in t.get("clips", [])), default=0.0)
    root = Element("xmeml", version="5")
    sequence = SubElement(root, "sequence", id="sequence-1")
    SubElement(sequence, "name").text = timeline.get("name") or project.get("title") or "formcut"
    SubElement(sequence, "duration").text = str(frames(end))
    _xml_rate(sequence, fps)
    timecode = SubElement(sequence, "timecode")
    _xml_rate(timecode, fps)
    SubElement(timecode, "string").text = "01:00:00:00"
    SubElement(timecode, "frame").text = str(3600 * _timebase(fps)[0])
    SubElement(timecode, "displayformat").text = "NDF"
    holder = SubElement(sequence, "media")
    video = SubElement(holder, "video")
    characteristics = SubElement(SubElement(video, "format"), "samplecharacteristics")
    SubElement(characteristics, "width").text = str(project.get("width") or 1920)
    SubElement(characteristics, "height").text = str(project.get("height") or 1080)
    _xml_rate(characteristics, fps)
    audio = SubElement(holder, "audio")
    written: dict[str, str] = {}
    count = 0
    for track in reversed(timeline["tracks"]):
        clips = sorted(track.get("clips", []), key=lambda c: c["start"])
        lane = SubElement(audio if clips and all(c.get("kind") == "audio" for c in clips) else video, "track")
        for clip in clips:
            name = clip.get("label") or clip.get("kind", "clip")
            if not clip.get("mediaId"):
                report.append(f"{name}: a {clip.get('kind', 'clip')} clip has no media file and is left out of FCP 7 XML")
                continue
            speed = float(clip.get("speed") or 1.0)
            if abs(speed - 1.0) > 1e-6:
                report.append(f"{name}: its speed ({speed:g}x) is not carried; it plays at normal speed")
            snapped = (frames(clip["start"] + clip["duration"]) - frames(clip["start"])) / fps
            if abs(clip["start"] * fps - frames(clip["start"])) > 1e-3 or abs(snapped - clip["duration"]) > 1e-3:
                report.append(f"{name}: snapped to whole frames at {fps:g} fps ({clip['duration']:.3f} s becomes {snapped:.3f} s)")
            count += 1
            item = SubElement(lane, "clipitem", id=f"clipitem-{count}")
            source_in = float(clip.get("sourceIn") or 0.0)
            known = library.get(clip["mediaId"], {})
            SubElement(item, "name").text = name
            SubElement(item, "enabled").text = "TRUE"
            SubElement(item, "duration").text = str(frames(float(known.get("duration") or source_in + clip["duration"])))
            _xml_rate(item, fps)
            SubElement(item, "start").text = str(frames(clip["start"]))
            SubElement(item, "end").text = str(frames(clip["start"] + clip["duration"]))
            SubElement(item, "in").text = str(frames(source_in))
            SubElement(item, "out").text = str(frames(source_in + clip["duration"]))
            if clip["mediaId"] in written:
                SubElement(item, "file", id=written[clip["mediaId"]])
                continue
            written[clip["mediaId"]] = f"file-{len(written) + 1}"
            file = SubElement(item, "file", id=written[clip["mediaId"]])
            SubElement(file, "name").text = known.get("name") or name
            path = _media_file(clip["mediaId"])
            SubElement(file, "pathurl").text = f"file://localhost{quote(path)}" if path else ""
            _xml_rate(file, fps)
            SubElement(file, "duration").text = str(frames(float(known.get("duration") or 0.0)))
            kinds = SubElement(file, "media")
            if clip.get("kind") in ("video", "image"):
                SubElement(kinds, "video")
            if clip.get("kind") in ("video", "audio"):
                SubElement(kinds, "audio")
    xml = tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n{xml}\n', report


def import_fcp7(text: str, media: list[dict]) -> tuple[dict, list[str]]:
    from urllib.parse import unquote

    # files from elsewhere: defusedxml refuses entity expansion and external entities
    from defusedxml.ElementTree import fromstring

    report: list[str] = []
    root = fromstring(text.split("<!DOCTYPE xmeml>")[-1].strip() if "<!DOCTYPE" in text else text)
    sequence = root if root.tag == "sequence" else root.find(".//sequence")
    if sequence is None:
        raise ValueError("No FCP 7 sequence in this file")
    timebase = int(sequence.findtext("rate/timebase") or 30)
    fps = timebase * 1000 / 1001 if (sequence.findtext("rate/ntsc") or "").upper() == "TRUE" else float(timebase)
    files: dict[str, tuple[str, str]] = {}
    for file in root.iter("file"):
        if file.find("name") is not None or file.find("pathurl") is not None:
            files[file.get("id", "")] = (file.findtext("name") or "", unquote(file.findtext("pathurl") or ""))

    def lanes(kind: str) -> list:
        return sequence.findall(f"media/{kind}/track")

    tracks = []
    for kind, label in (("video", "V"), ("audio", "A")):
        ordered = list(reversed(lanes(kind))) if kind == "video" else lanes(kind)
        for number, lane in enumerate(ordered, start=1):
            name = f"{label}{len(ordered) - number + 1 if kind == 'video' else number}"
            out = {"id": str(uuid.uuid4()), "name": name, "clips": []}
            for element in lane:
                if element.tag in ("transitionitem", "generatoritem"):
                    report.append(
                        f"{name}: a {element.tag} ({element.findtext('name') or element.findtext('effect/name') or ''}) is not carried"
                    )
                    continue
                if element.tag != "clipitem":
                    continue
                start, end = int(element.findtext("start") or -1), int(element.findtext("end") or -1)
                source_in = int(element.findtext("in") or 0)
                if start < 0 or end < 0:
                    report.append(f"{name}: {element.findtext('name')} sits on a transition edge and is left out")
                    continue
                file = element.find("file")
                file_name, path = files.get(file.get("id", "") if file is not None else "", (element.findtext("name") or "", ""))
                found = _match(file_name or element.findtext("name") or "", path, media)
                if not found:
                    report.append(f"{name}: {file_name or element.findtext('name')} is not in the media library")
                    continue
                clip = {
                    "id": str(uuid.uuid4()),
                    "kind": found["kind"],
                    "label": found["name"],
                    "start": round(start / fps, 6),
                    "duration": round((end - start) / fps, 6),
                    "mediaId": found["id"],
                    "sourceIn": round(source_in / fps, 6),
                }
                if found["kind"] == "video":
                    clip["filmstrip"] = True
                out["clips"].append(clip)
            tracks.append(out)
    if not tracks:
        raise ValueError("The sequence has no tracks")
    return {"id": str(uuid.uuid4()), "name": sequence.findtext("name") or "Imported XML", "tracks": tracks}, report


# ----------------------------------------------------------------------------------------------- FCPXML


def _fcp_time(seconds: float, fps: float) -> str:
    """Rational seconds on the frame grid: 75/30s at 30 fps, multiples of 1001/30000s at 29.97."""
    timebase, ntsc = _timebase(fps)
    frames = round(seconds * fps)
    if frames == 0:
        return "0s"
    return f"{frames * 1001}/{timebase * 1000}s" if ntsc else f"{frames}/{timebase}s"


def _fcp_seconds(value: str | None) -> float:
    if not value:
        return 0.0
    text = value.strip().rstrip("s")
    if "/" in text:
        top, bottom = text.split("/", 1)
        return float(top) / float(bottom)
    return float(text)


def export_fcpxml(project: dict, media: list[dict], timeline_index: int | None = None) -> tuple[str, list[str]]:
    """FCPXML 1.10. FCP has no tracks: formcut's bottom video track is the primary storyline (spine) with gaps; video
    tracks above it are connected clips on lanes 1, 2...; audio tracks on lanes -1, -2... Each connected clip hangs on
    the spine item holding its start, its offset in that item's time."""
    from urllib.parse import quote
    from xml.etree.ElementTree import Element, SubElement, tostring

    fps = float(project.get("fps") or 30)
    timebase, ntsc = _timebase(fps)
    index = project.get("activeTimeline", 0) if timeline_index is None else timeline_index
    timeline = project["timelines"][index]
    report: list[str] = []
    library = {item["id"]: item for item in media}
    tracks = timeline["tracks"]
    end = max((c["start"] + c["duration"] for t in tracks for c in t.get("clips", [])), default=0.0)
    root = Element("fcpxml", version="1.10")
    resources = SubElement(root, "resources")
    SubElement(
        resources,
        "format",
        id="r1",
        frameDuration=f"1001/{timebase * 1000}s" if ntsc else f"1/{timebase}s",
        width=str(project.get("width") or 1920),
        height=str(project.get("height") or 1080),
    )
    assets: dict[str, str] = {}

    def asset(clip: dict) -> str:
        if clip["mediaId"] not in assets:
            assets[clip["mediaId"]] = f"r{len(assets) + 2}"
            known = library.get(clip["mediaId"], {})
            path = _media_file(clip["mediaId"]) or ""
            element = SubElement(
                resources,
                "asset",
                id=assets[clip["mediaId"]],
                name=known.get("name") or clip.get("label") or "media",
                start="0s",
                duration=_fcp_time(float(known.get("duration") or 0.0), fps),
                hasVideo="1" if clip.get("kind") in ("video", "image") else "0",
                hasAudio="1" if clip.get("kind") in ("video", "audio") else "0",
                format="r1",
            )
            SubElement(element, "media-rep", kind="original-media", src=f"file://{quote(path)}")
        return assets[clip["mediaId"]]

    def media_clips(track: dict) -> list[dict]:
        kept = []
        for clip in sorted(track.get("clips", []), key=lambda c: c["start"]):
            name = clip.get("label") or clip.get("kind", "clip")
            if not clip.get("mediaId"):
                report.append(f"{name}: a {clip.get('kind', 'clip')} clip has no media file and is left out of FCPXML")
                continue
            if abs(float(clip.get("speed") or 1.0) - 1.0) > 1e-6:
                report.append(f"{name}: its speed is not carried; it plays at normal speed")
            snapped = (round((clip["start"] + clip["duration"]) * fps) - round(clip["start"] * fps)) / fps
            if abs(clip["start"] * fps - round(clip["start"] * fps)) > 1e-3 or abs(snapped - clip["duration"]) > 1e-3:
                report.append(f"{name}: snapped to whole frames at {fps:g} fps ({clip['duration']:.3f} s becomes {snapped:.3f} s)")
            kept.append(clip)
        return kept

    def clip_element(parent, clip: dict, offset: float, lane: int | None = None):
        attributes = {
            "ref": asset(clip),
            "name": clip.get("label") or "clip",
            "offset": _fcp_time(offset, fps),
            "start": _fcp_time(float(clip.get("sourceIn") or 0.0), fps),
            "duration": _fcp_time(clip["duration"], fps),
        }
        if lane is not None:
            attributes["lane"] = str(lane)
        if clip.get("kind") == "video":
            attributes["format"] = "r1"
        return SubElement(parent, "asset-clip", attributes)

    video = [i for i, t in enumerate(tracks) if not (t.get("clips") and all(c.get("kind") == "audio" for c in t["clips"]))]
    audio = [i for i in range(len(tracks)) if i not in video]
    base = video[-1] if video else None
    event = SubElement(SubElement(root, "library"), "event", name="formcut")
    project_element = SubElement(event, "project", name=timeline.get("name") or "formcut")
    sequence = SubElement(project_element, "sequence", format="r1", duration=_fcp_time(end, fps), tcStart="0s", tcFormat="NDF")
    spine = SubElement(sequence, "spine")
    holders: list[tuple[float, float, float, object]] = []  # (offset, duration, start in its own time, element)

    def gap(at: float, length: float) -> tuple[float, float, float, object]:
        element = SubElement(spine, "gap", name="Gap", offset=_fcp_time(at, fps), start="0s", duration=_fcp_time(length, fps))
        return (at, length, 0.0, element)

    position = 0.0
    for clip in media_clips(tracks[base]) if base is not None else []:
        if clip["start"] > position + 1e-6:
            holders.append(gap(position, clip["start"] - position))
        element = clip_element(spine, clip, clip["start"])
        holders.append((clip["start"], clip["duration"], float(clip.get("sourceIn") or 0.0), element))
        position = clip["start"] + clip["duration"]
    if end > position + 1e-6:
        holders.append(gap(position, end - position))
    lanes = [(i, n) for n, i in enumerate(reversed(video[:-1]), start=1)] + [(i, -n) for n, i in enumerate(audio, start=1)]
    for track_index, lane in lanes:
        for clip in media_clips(tracks[track_index]):
            holder = next((h for h in holders if h[0] - 1e-6 <= clip["start"] < h[0] + h[1] - 1e-6), holders[-1] if holders else None)
            if holder is None:
                continue
            clip_element(holder[3], clip, holder[2] + (clip["start"] - holder[0]), lane)
    xml = tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n{xml}\n', report


def import_fcpxml(text: str, media: list[dict]) -> tuple[dict, list[str]]:
    from urllib.parse import unquote

    # files from elsewhere: defusedxml refuses entity expansion and external entities
    from defusedxml.ElementTree import fromstring

    report: list[str] = []
    root = fromstring(text.split("<!DOCTYPE fcpxml>")[-1].strip() if "<!DOCTYPE" in text else text)
    sequence = root.find(".//sequence")
    spine = sequence.find("spine") if sequence is not None else None
    if spine is None:
        raise ValueError("No FCPXML sequence in this file")
    assets = {}
    for element in root.iter("asset"):
        rep = element.find("media-rep")
        source = unquote((rep.get("src") if rep is not None else element.get("src")) or "")
        assets[element.get("id")] = (element.get("name") or "", source, _fcp_seconds(element.get("start")))
    lanes: dict[int, list[dict]] = {}

    def place(element, at: float, lane: int) -> None:
        # an asset-clip names its asset; a clip (as OTIO's adapter and other tools write) wraps a video or audio element
        # that does, possibly inside a gap, and its source point is the clip's start in that element's time
        if element.tag == "asset-clip":
            ref, source_point = element.get("ref"), _fcp_seconds(element.get("start"))
        elif element.tag == "clip":
            inner = next((e for e in element.iter() if e.tag in ("video", "audio") and e.get("ref")), None)
            if inner is None:
                report.append(f"lane {lane}: the clip {element.get('name') or ''} holds no media")
                return
            ref = inner.get("ref")
            source_point = _fcp_seconds(element.get("start")) - _fcp_seconds(inner.get("offset")) + _fcp_seconds(inner.get("start"))
        else:
            if element.tag != "gap":
                report.append(f"lane {lane}: a {element.tag} ({element.get('name') or ''}) is not carried")
            return
        name, source, asset_start = assets.get(ref, ("", "", 0.0))
        found = _match(name or element.get("name") or "", source, media)
        if not found:
            report.append(f"{element.get('name') or name}: not in the media library")
            return
        clip = {
            "id": str(uuid.uuid4()),
            "kind": found["kind"],
            "label": found["name"],
            "start": round(at, 6),
            "duration": round(_fcp_seconds(element.get("duration")), 6),
            "mediaId": found["id"],
            "sourceIn": round(max(0.0, source_point - asset_start), 6),
        }
        if found["kind"] == "video":
            clip["filmstrip"] = True
        lanes.setdefault(lane, []).append(clip)

    for item in spine:
        at = _fcp_seconds(item.get("offset"))
        if item.tag == "transition":
            report.append("a transition on the primary storyline is not carried; the cut stays")
            continue
        place(item, at, 0)
        own_start = _fcp_seconds(item.get("start"))
        for child in item:
            if child.get("lane") is None:
                continue
            place(child, at + _fcp_seconds(child.get("offset")) - own_start, int(child.get("lane")))
    if not lanes:
        raise ValueError("The sequence holds no media clips formcut can carry")
    tracks = []
    for lane in sorted(lanes, reverse=True):
        name = f"V{lane + 1}" if lane >= 0 else f"A{-lane}"
        tracks.append({"id": str(uuid.uuid4()), "name": name, "clips": sorted(lanes[lane], key=lambda c: c["start"])})
    project = root.find(".//project")
    name = (project.get("name") if project is not None else None) or "Imported FCPXML"
    return {"id": str(uuid.uuid4()), "name": name, "tracks": tracks}, report


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
        document, report = export_otio(body.project, body.timeline, list_media())
        data, media_type, suffix = json.dumps(document, indent=2), "application/json", "otio"
    elif fmt == "edl":
        data, report = export_edl(body.project, body.track, body.timeline)
        media_type, suffix = "text/plain", "edl"
    elif fmt == "fcp7":
        data, report = export_fcp7(body.project, list_media(), body.timeline)
        media_type, suffix = "application/xml", "xml"
    elif fmt == "fcpxml":
        data, report = export_fcpxml(body.project, list_media(), body.timeline)
        media_type, suffix = "application/xml", "fcpxml"
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
        elif fmt == "fcp7":
            timeline, report = import_fcp7(body.text, media)
        elif fmt == "fcpxml":
            timeline, report = import_fcpxml(body.text, media)
        else:
            raise HTTPException(404, f"No importer for {fmt}")
    except (ValueError, KeyError, TypeError, SyntaxError) as exc:
        raise HTTPException(422, f"Could not read this {fmt.upper()} file: {exc}") from None
    return {"timeline": timeline, "report": report}
