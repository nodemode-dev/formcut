"""Frame cache and read-ahead for preview sessions (R1).

A cached frame is keyed by its time and by the signature of every clip that
covers that time, so an edit to one clip drops only the frames its span
touches; everything else replays from memory at the project rate. Read-ahead
renders a short run past the playhead on a single background worker per
session, which keeps the decoder's sequential read pattern intact.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict


def clip_signature(clip: dict) -> str:
    """Everything about a clip that can change its pixels."""
    return hashlib.sha1(json.dumps(clip, sort_keys=True, default=str).encode()).hexdigest()[:16]


def covering(project: dict, at: float) -> list[dict]:
    active = project["activeTimeline"]
    found = []
    for track in project["timelines"][active]["tracks"]:
        for clip in track["clips"]:
            if clip["start"] <= at < clip["start"] + clip["duration"] + clip.get("extendOut", 0):
                found.append(clip)
    return found


class FrameCache:
    """Bounded, content-addressed store of rendered frames for one session."""

    def __init__(self, project: dict, limit: int = 240):
        self.project = project
        self.limit = limit
        self.frames: OrderedDict[tuple[int, str], object] = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.rendered = 0

    def key(self, at: float) -> tuple[int, str]:
        stamp = round(at * 1000)
        parts = sorted(clip_signature(clip) for clip in covering(self.project, at))
        return (stamp, "-".join(parts))

    def get(self, at: float):
        with self.lock:
            key = self.key(at)
            frame = self.frames.get(key)
            if frame is None:
                self.misses += 1
                return None
            self.frames.move_to_end(key)
            self.hits += 1
            return frame

    def put(self, at: float, frame) -> None:
        with self.lock:
            self.frames[self.key(at)] = frame
            self.frames.move_to_end(self.key(at))
            self.rendered += 1
            while len(self.frames) > self.limit:
                self.frames.popitem(last=False)

    def invalidate_span(self, start: float, end: float) -> int:
        """Drop frames inside a time span; returns how many went."""
        with self.lock:
            doomed = [k for k in self.frames if start * 1000 - 1 <= k[0] <= end * 1000 + 1]
            for key in doomed:
                self.frames.pop(key, None)
            return len(doomed)

    def retarget(self, project: dict) -> int:
        """Point at an edited document and drop only what its changes touched.

        Frames whose covering clips still hash the same stay; a frame that any
        changed clip covers goes, so one clip's edit never costs the timeline.
        """
        with self.lock:
            before = {clip["id"]: clip_signature(clip) for clip in _all_clips(self.project)}
            after = {clip["id"]: clip_signature(clip) for clip in _all_clips(project)}
            changed = [clip for clip in _all_clips(project) if before.get(clip["id"]) != after[clip["id"]]]
            gone = [clip for clip in _all_clips(self.project) if clip["id"] not in after]
            self.project = project
            dropped = 0
            for clip in changed + gone:
                dropped += self.invalidate_span(clip["start"], clip["start"] + clip["duration"])
            return dropped

    def stats(self) -> dict:
        with self.lock:
            return {"cached": len(self.frames), "hits": self.hits, "misses": self.misses, "rendered": self.rendered}


def _all_clips(project: dict) -> list[dict]:
    return [clip for timeline in project["timelines"] for track in timeline["tracks"] for clip in track["clips"]]


class ReadAhead:
    """Renders a short run past the playhead on one background worker."""

    def __init__(self, render, cache: FrameCache, fps: float, ahead: float = 1.5):
        self.render = render
        self.cache = cache
        self.fps = max(1.0, float(fps))
        self.ahead = ahead
        self.target = 0.0
        self.wake = threading.Event()
        self.stopped = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def seek(self, at: float) -> None:
        self.target = at
        self.wake.set()

    def stop(self) -> None:
        self.stopped = True
        self.wake.set()
        self.thread.join(timeout=2)

    def _run(self) -> None:
        while not self.stopped:
            self.wake.wait(timeout=0.5)
            self.wake.clear()
            start = self.target
            step = 1 / self.fps
            count = max(1, int(self.ahead * self.fps))
            for index in range(1, count + 1):
                if self.stopped or self.target != start:
                    break
                at = start + index * step
                if at > self.cache.project.get("duration", 0):
                    break
                if self.cache.get(at) is not None:
                    continue
                try:
                    self.cache.put(at, self.render(at))
                except Exception:
                    break
