"""Frame integrity: which source frames are new, which output frames would repeat, and how to cut so none do.

From the owner's Posh cutdowns: a 60p master carrying 24, 25 and 30p footage padded with duplicates; rendered at 30
fps the spots repeated frames on every 24 and 25p shot (35 to 40% flagged), and a hand-made solver picked in-points
and 1% speed-ups so every output frame landed on a distinct source frame, with a slow push on holds.

- The cadence map: each source frame's share of pixels changed by over 4 levels from the frame before (at 480 by
  270). True duplicates change 0.00 to 0.07%; a frame is new above the larger of 0.15% and 5% of the new-frame level
  around it (24 frames). On the Posh master this predicts the seven delivered spots' zero repeats.
- Frame choice: output frame k of a clip shows source frame floor((sourceIn + (k / rate - start) * speed) * fps),
  as the renderer reads it.
- The solver: per clip, the smallest source shift (up to 3 frames) and speed-up (up to 2%) with no predicted repeat;
  a clip that cannot be freed (a hold) gets a keep-alive push, 0.10% scale an output frame.
- The mpdecimate simulator: ffmpeg's rule (8x8 block differences on a 4-pixel grid against the last kept frame, per
  YUV 4:2:0 plane, hi 768, lo 320, frac 0.33), matching ffmpeg's own decisions frame for frame.
"""

from pathlib import Path

import cv2
import numpy as np

from .paths import DATA_DIR

CACHE = DATA_DIR / "cadence"
HI, LO, FRAC = 64 * 12, 64 * 5, 0.33
PUSH_PER_FRAME = 0.10  # percent scale an output frame: enough that no frame of a hold repeats its predecessor


def changed_shares(path: Path, report=None, cancelled=None) -> np.ndarray:
    """Each frame's share of pixels changed by over 4 levels from the frame before (the first frame 1.0)."""
    capture = cv2.VideoCapture(str(path))
    total = max(1, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    previous, shares = None, []
    while True:
        if cancelled and cancelled():
            raise InterruptedError
        ok, frame = capture.read()
        if not ok:
            break
        small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (480, 270), interpolation=cv2.INTER_AREA).astype(np.int16)
        shares.append(float((np.abs(small - previous) > 4).mean()) if previous is not None else 1.0)
        previous = small
        if report and len(shares) % 60 == 0:
            report(len(shares) / total, f"frame {len(shares)} of {total}")
    capture.release()
    return np.array(shares, np.float32)


def new_frames(shares: np.ndarray) -> np.ndarray:
    """True where a frame shows a new picture: its change above 0.15% and 5% of the new-frame level around it."""
    new = np.zeros(len(shares), bool)
    if len(shares):
        new[0] = True
    for i in range(1, len(shares)):
        around = np.sort(shares[max(1, i - 12) : i + 13])
        level = float(np.median(around[-max(1, int(0.4 * len(around))) :]))
        new[i] = shares[i] > max(0.0015, 0.05 * level)
    return new


def cadence_map(media_id: str, path: Path, report=None, cancelled=None) -> np.ndarray:
    """The picture number of each source frame (it changes only on a new frame), cached per media."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{media_id}.npy"
    if cached.exists():
        return np.load(cached)
    pictures = np.cumsum(new_frames(changed_shares(path, report, cancelled)))
    np.save(cached, pictures)
    return pictures


def summary(pictures: np.ndarray, fps: float) -> dict:
    """New pictures per second through the media, and where it holds (no new picture for half a second or more)."""
    seconds = int(len(pictures) // fps)
    per_second = [int(pictures[min(len(pictures) - 1, int((s + 1) * fps) - 1)] - pictures[int(s * fps)]) for s in range(seconds)]
    holds, run = [], 0
    steps = np.diff(pictures, prepend=pictures[:1] - 1) if len(pictures) else np.array([])
    for i, step in enumerate(steps):
        run = run + 1 if step == 0 else 0
        if run == round(fps / 2):
            holds.append(round((i - run + 1) / fps, 3))
    total = int(pictures[-1]) if len(pictures) else 0
    return {"frames": len(pictures), "fps": fps, "pictures": total, "per_second": per_second, "holds": holds}


def source_frames(clip: dict, rate: float, fps: float, count: int, source_in: float | None = None, speed: float | None = None) -> list[int]:
    """The source frame each output frame of a clip shows: floor((sourceIn + (k / rate - start) * speed) * fps)."""
    begin = clip.get("sourceIn", 0) if source_in is None else source_in
    pace = clip.get("speed", 1) if speed is None else speed
    first, last = round(clip["start"] * rate), round((clip["start"] + clip["duration"]) * rate)
    return [min(count - 1, max(0, int((begin + (k / rate - clip["start"]) * pace) * fps + 1e-7))) for k in range(first, last)]


def repeats(frames: list[int], pictures: np.ndarray) -> list[int]:
    """Positions in a clip's output where the picture is the one before (a repeat)."""
    shown = [int(pictures[f]) for f in frames]
    return [j for j in range(1, len(shown)) if shown[j] == shown[j - 1]]


def pushed(clip: dict) -> bool:
    """A clip whose scale is keyframed: every output frame differs, whatever the source does."""
    return any("scale" in (key.get("props") or {}) for key in clip.get("keyframes") or [])


def solve_clip(clip: dict, rate: float, fps: float, pictures: np.ndarray) -> dict:
    """The smallest change that leaves a clip with no repeated picture: a source shift of up to 3 frames and a speed-up
    of up to 2%, tried smallest first; a clip none frees (a hold) gets the keep-alive push."""
    count = len(pictures)
    base_in, base_speed = clip.get("sourceIn", 0), clip.get("speed", 1)
    before = len(repeats(source_frames(clip, rate, fps, count), pictures))
    if before == 0 or pushed(clip):
        return {"repeats": before if not pushed(clip) else 0, "change": None}
    candidates = [(shift, extra) for shift in range(-3, 4) for extra in (0.0, 0.005, 0.01, 0.015, 0.02)]
    for shift, extra in sorted(candidates, key=lambda option: abs(option[0]) + 10 * option[1]):
        start = max(0.0, base_in + shift / fps)
        speed = round(base_speed * (1 + extra), 4)
        # the clip's last source frame stays inside the media
        if int((start + clip["duration"] * speed) * fps) >= count:
            continue
        if not repeats(source_frames(clip, rate, fps, count, start, speed), pictures):
            return {"repeats": before, "change": {"sourceIn": round(start, 6), "speed": speed}}
    frames = max(1, round(clip["duration"] * rate))
    end = round(100 * (1 + PUSH_PER_FRAME / 100) ** frames, 4)
    push = [
        {"t": 0, "props": {"scale": 100}, "interp": "linear"},
        {"t": round(clip["duration"], 6), "props": {"scale": end}, "interp": "linear"},
    ]
    return {"repeats": before, "change": {"keyframes": push}}


def _plane_differs(current: np.ndarray, reference: np.ndarray) -> bool:
    h, w = current.shape
    difference = cv2.absdiff(current, reference).astype(np.float32)
    sad = cv2.boxFilter(difference, -1, (8, 8), normalize=False, anchor=(0, 0), borderType=cv2.BORDER_CONSTANT)
    grid = sad[0 : h - 7 : 4, 8 : w - 7 : 4]
    if (grid > HI).any():
        return True
    return int((grid > LO).sum()) > int((w // 16) * (h // 16) * FRAC)


def mpdecimate_drops(frames) -> list[int]:
    """The frames ffmpeg's mpdecimate drops, from an iterable of (Y, U, V) 4:2:0 planes: a frame none of whose planes
    differs from the last kept frame."""
    dropped, reference = [], None
    for index, planes in enumerate(frames):
        if reference is None or any(_plane_differs(c, r) for c, r in zip(planes, reference, strict=True)):
            reference = planes
        else:
            dropped.append(index)
    return dropped
