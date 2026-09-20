"""Carrying a mask forward, framing a subject, and cutting the ums.

Three things, all of which return times and numbers a person can inspect and
change rather than a processed result they must accept.

**Tracking.** A mask drawn on one frame is wrong by the next one if anything
moves. Following it with optical flow means a subject can be masked once and
stay masked, which is the difference between a mask being useful on a moving
shot and being an afternoon of keyframes.

**Auto reframe.** Turning a wide shot into a tall one means deciding what to
keep, and the honest answer is usually "whatever is moving, and whatever the
subject is". The path is smoothed, because a crop that chases every twitch is
worse than one that lags slightly.

**Filler words.** Ums and likes are found in the transcript, not the audio, so
the ranges handed back line up with words a person can read and veto before
anything is cut.
"""

from __future__ import annotations

import cv2
import numpy as np

# Kept deliberately small and explicit rather than clever: a list a person can
# read, argue with, and add their own to.
FILLERS = {
    "en": [
        "um",
        "uh",
        "erm",
        "ah",
        "like",
        "you know",
        "i mean",
        "sort of",
        "kind of",
        "basically",
        "actually",
        "literally",
        "right",
        "so yeah",
    ],
    "es": ["eh", "este", "o sea", "bueno", "pues", "digamos"],
    "de": ["äh", "ähm", "also", "halt", "eben", "sozusagen"],
}


def _grey(frame: np.ndarray, width: int = 480) -> np.ndarray:
    if frame.ndim == 3:
        frame = cv2.cvtColor(frame[:, :, :3], cv2.COLOR_RGB2GRAY)
    if frame.shape[1] != width:
        height = max(1, round(frame.shape[0] * width / frame.shape[1]))
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    return frame.astype(np.uint8)


def track_points(frames: list[np.ndarray], points: list[dict]) -> list[dict]:
    """Follow mask anchors across frames.

    Anchors are not tracked individually, because an anchor is usually placed on
    an edge or in the middle of something flat, and a point with no gradient
    under it cannot be followed: track a corner and it moves, track the middle
    of a white square and it sits still while the square leaves. So the features
    worth tracking are found inside the mask instead, their movement is measured,
    and the whole outline is moved by what they did. A point that cannot be found
    is dropped from the estimate rather than dragging it somewhere invented.
    """
    if not frames or not points:
        return []
    first = _grey(frames[0])
    height, width = first.shape
    anchors = np.array([[p["x"] * width, p["y"] * height] for p in points], np.float32)

    def record(index: int, positions: np.ndarray) -> dict:
        return {"t": index, "points": [{"x": round(float(x) / width, 5), "y": round(float(y) / height, 5)} for x, y in positions]}

    # Features inside the mask: what actually has texture to follow.
    region = np.zeros((height, width), np.uint8)
    cv2.fillPoly(region, [anchors.astype(np.int32)], 255)
    features = cv2.goodFeaturesToTrack(first, maxCorners=120, qualityLevel=0.01, minDistance=6, mask=region)
    if features is None or len(features) < 3:
        # Nothing to follow inside it, so widen to the whole frame and rely on
        # the dominant motion, which is right for a camera move.
        features = cv2.goodFeaturesToTrack(first, maxCorners=120, qualityLevel=0.01, minDistance=6)
    if features is None or len(features) < 3:
        return [record(index, anchors) for index in range(len(frames))]

    path = [record(0, anchors)]
    previous, tracked, current = first, features.astype(np.float32), anchors.copy()
    for index, frame in enumerate(frames[1:], start=1):
        grey = _grey(frame)
        moved, found, _ = cv2.calcOpticalFlowPyrLK(
            previous,
            grey,
            tracked,
            None,
            winSize=(21, 21),
            maxLevel=3,
            criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
        )
        if moved is not None and found is not None:
            keep = found.reshape(-1) == 1
            if keep.sum() >= 3:
                before = tracked.reshape(-1, 2)[keep]
                after = moved.reshape(-1, 2)[keep]
                # The median shift, so a few features latching onto the
                # background do not drag the mask with them.
                shift = np.median(after - before, axis=0)
                current = current + shift
                tracked = after.reshape(-1, 1, 2).astype(np.float32)
        path.append(record(index, current))
        previous = grey
    return path


def reframe(frames: list[np.ndarray], aspect: float = 9 / 16, smoothing: float = 0.8) -> dict:
    """Where to put a crop of a given shape, over time.

    Interest is taken from motion between frames and from edge density, which
    together find a moving subject without needing a model. The result is
    smoothed heavily, because a crop that chases every twitch reads worse than
    one that lags.
    """
    if not frames:
        return {"crops": [], "aspect": aspect}
    grey = [_grey(frame) for frame in frames]
    height, width = grey[0].shape
    crop_w = min(width, round(height * aspect))
    half = crop_w / 2

    centres: list[float] = []
    for index, frame in enumerate(grey):
        motion = None
        if index > 0:
            motion = cv2.absdiff(frame, grey[index - 1]).astype(np.float32)
        detail = cv2.Laplacian(frame, cv2.CV_32F)
        np.abs(detail, out=detail)
        interest = detail if motion is None else detail + motion * 3.0
        columns = interest.sum(axis=0)
        if columns.sum() <= 0:
            centres.append(width / 2)
            continue
        # The centre of mass of interest, which sits between two subjects rather
        # than picking one and jumping between them.
        centres.append(float((columns * np.arange(width)).sum() / columns.sum()))

    smoothing = max(0.0, min(0.99, smoothing))
    smoothed: list[float] = []
    value = centres[0]
    for centre in centres:
        value = value * smoothing + centre * (1 - smoothing)
        smoothed.append(value)
    # A second pass backwards, so the path does not lag the subject overall.
    value = smoothed[-1]
    for index in range(len(smoothed) - 1, -1, -1):
        value = value * smoothing + smoothed[index] * (1 - smoothing)
        smoothed[index] = value

    crops = []
    for index, centre in enumerate(smoothed):
        left = max(0.0, min(width - crop_w, centre - half))
        crops.append({"t": index, "x": round(left / width, 5), "w": round(crop_w / width, 5)})
    return {"crops": crops, "aspect": aspect, "width": crop_w, "of": width}


def fillers(segments: list[dict], language: str = "en", extra: list[str] | None = None) -> dict:
    """Ranges in a transcript that are filler, to be cut or kept.

    Nothing is removed here. What comes back is a list of ranges with the word
    that matched, so a person sees what would go before any of it does.
    """
    words = list(FILLERS.get(language, FILLERS["en"]))
    words += [w.strip().lower() for w in (extra or []) if w.strip()]
    words.sort(key=len, reverse=True)

    found = []
    for segment in segments:
        text = str(segment.get("text") or "").lower()
        if not text.strip():
            continue
        stripped = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in text)
        spoken = stripped.split()
        if not spoken:
            continue
        start = float(segment.get("start", 0))
        end = float(segment.get("end", start))
        span = max(0.001, end - start)
        per_word = span / len(spoken)
        index = 0
        while index < len(spoken):
            matched = None
            for phrase in words:
                parts = phrase.split()
                if spoken[index : index + len(parts)] == parts:
                    matched = (phrase, len(parts))
                    break
            if matched:
                phrase, length = matched
                found.append(
                    {
                        "start": round(start + index * per_word, 3),
                        "end": round(start + (index + length) * per_word, 3),
                        "word": phrase,
                    }
                )
                index += length
            else:
                index += 1

    merged: list[dict] = []
    for item in sorted(found, key=lambda entry: entry["start"]):
        if merged and item["start"] - merged[-1]["end"] < 0.08:
            merged[-1]["end"] = max(merged[-1]["end"], item["end"])
            merged[-1]["word"] += " " + item["word"]
        else:
            merged.append(dict(item))
    total = round(sum(item["end"] - item["start"] for item in merged), 2)
    return {"ranges": merged, "count": len(merged), "seconds": total}
