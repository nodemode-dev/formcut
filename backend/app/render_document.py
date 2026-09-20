import copy
import math

from .catalogue import TRANSITIONS
from .validation import clip_values


def validate_document(project: dict) -> dict:
    result = copy.deepcopy(project)
    for field, low, high, default in [("width", 16, 7680, 1920), ("height", 16, 7680, 1080), ("fps", 1, 120, 30)]:
        value = result.get(field, default)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value or not low <= value <= high:
            raise ValueError(f"Invalid project {field}")
        result[field] = int(value)
    timelines = result.get("timelines")
    active = result.get("activeTimeline", 0)
    if not isinstance(timelines, list) or not timelines or not isinstance(active, int) or not 0 <= active < len(timelines):
        raise ValueError("Project needs an active timeline")
    for timeline in timelines:
        if not isinstance(timeline, dict):
            raise ValueError("Every timeline needs a track list")
        for field, low, high in [("width", 16, 7680), ("height", 16, 7680), ("fps", 1, 120)]:
            value = timeline.get(field)
            if value is None:
                continue
            if not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value or not low <= value <= high:
                raise ValueError(f"Invalid timeline {field}")
            timeline[field] = int(value)
    # The active timeline's format wins; a timeline without its own keeps the project's.
    for field in ("width", "height", "fps"):
        override = timelines[active].get(field)
        if override:
            result[field] = int(override)
    all_tracks = []
    for timeline in timelines:
        if not isinstance(timeline, dict) or not isinstance(timeline.get("tracks"), list):
            raise ValueError("Every timeline needs a track list")
        if len(timeline["tracks"]) > 128:
            raise ValueError("Timeline exceeds the track limit")
        all_tracks.extend(timeline["tracks"])
    tracks = timelines[active]["tracks"]
    ids = set()
    for track in all_tracks:
        if not isinstance(track, dict) or not isinstance(track.get("clips"), list):
            raise ValueError("Track clips must be an array")
        for clip in track["clips"]:
            if not isinstance(clip, dict):
                raise ValueError("Clip must be an object")
            if clip.get("id") in ids or not isinstance(clip.get("id"), str):
                raise ValueError("Clip ids must be unique")
            ids.add(clip["id"])
            clip_values(clip)
            for key in ["start", "duration"]:
                value = clip.get(key)
                if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0 or value > 86400:
                    raise ValueError(f"Invalid clip {key}")
            if clip["duration"] <= 0 or clip.get("kind") not in ("video", "image", "audio", "text", "filter"):
                raise ValueError("Invalid clip duration or kind")
            if len(clip.get("effects") or []) > 32 or len(clip.get("speedCurve") or []) > 256:
                raise ValueError("Clip processing limit exceeded")
    if len(ids) > 10000:
        raise ValueError("Timeline exceeds the clip limit")
    result["duration"] = max([c["start"] + c["duration"] for t in tracks for c in t["clips"]] or [0.1])
    return result


def flatten(project: dict) -> list[dict]:
    tracks = project["timelines"][project.get("activeTimeline", 0)]["tracks"]
    all_clips = []
    for index, track in enumerate(tracks):
        clips = sorted(copy.deepcopy(track["clips"]), key=lambda c: c["start"])
        for i, clip in enumerate(clips):
            clip["trackIndex"] = index
            clip["trackHidden"] = bool(track.get("hidden"))
            clip["muted"] = bool(track.get("muted") or clip.get("muted"))
            previous = clips[i - 1] if i else None
            transition = clip.get("transitionIn")
            if transition:
                kind = transition.get("type")
                if kind not in TRANSITIONS:
                    raise ValueError("Unknown transition")
                length = min(clip["duration"] / 2, max(0.01, float(transition.get("duration", 0.5))))
                clip["transitionIn"]["duration"] = length
                adjacent = previous and abs(previous["start"] + previous["duration"] - clip["start"]) < 0.05
                if kind == "dip":
                    clip["rampIn"] = length / 2
                    if adjacent:
                        previous["rampOut"] = length / 2
                else:
                    clip["transitionLength"] = length
                    if adjacent:
                        previous["extendOut"] = length
                        # T1: the outgoing clip is not a still backdrop. It keeps
                        # drawing through the band and takes the other half of
                        # the move, so a wipe uncovers it, a slide carries it off
                        # and a zoom pushes it away, rather than it sitting
                        # motionless while only the incoming clip animates.
                        previous["transitionOut"] = {"type": kind, "length": length}
                        if kind == "push-up":
                            previous["pushOut"] = length
                    if kind == "crossfade":
                        clip["rampIn"] = length
        all_clips.extend(clips)
    return all_clips
