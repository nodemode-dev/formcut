"""Beats, and getting music out of the way of a voice.

Two things the comparison found in neither editor, and both are arithmetic on
samples rather than anything that needs a model or a GPU.

**Beats.** Cutting to music by hand means scrubbing for the downbeat and
nudging a clip until it feels right. Finding the beats once and handing back
their times lets the interface snap to them instead.

**Ducking.** Music under speech has to come down when the speech starts and back
up when it stops, and doing that by hand is a row of keyframes per sentence.
Given the speech track and the music track, this works out where the speech is
and returns the envelope the music should follow.

Neither guesses: both are derived from the samples and return times a person can
see and adjust.
"""

from __future__ import annotations

import numpy as np

RATE = 48000


def _envelope(samples: np.ndarray, rate: int, hop: float = 0.01) -> tuple[np.ndarray, float]:
    """Short-term loudness, one value per hop."""
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    step = max(1, int(rate * hop))
    usable = len(samples) - len(samples) % step
    if usable <= 0:
        return np.zeros(0, np.float32), hop
    frames = samples[:usable].reshape(-1, step)
    return np.sqrt((frames.astype(np.float32) ** 2).mean(axis=1)), hop


def beats(samples: np.ndarray, rate: int = RATE, sensitivity: float = 0.5) -> dict:
    """Where the beats are, and the tempo they imply.

    Onsets are found from the rise in loudness rather than its level, because a
    beat is an attack: what matters is the jump, not how loud the passage is.
    The tempo comes from the most common spacing between onsets, which is
    steadier than averaging them when a few are missed or doubled.
    """
    level, hop = _envelope(samples, rate)
    if len(level) < 8:
        return {"beats": [], "bpm": None, "count": 0}

    # The rise, half-wave rectified: only increases count as an onset.
    rise = np.diff(level, prepend=level[0])
    rise[rise < 0] = 0
    if rise.max() <= 0:
        return {"beats": [], "bpm": None, "count": 0}
    rise /= rise.max()

    # A threshold relative to the local average, so a quiet passage still gives
    # up its beats and a loud one does not give up every sample.
    window = max(3, int(0.35 / hop))
    padded = np.pad(rise, (window, window), mode="edge")
    local = np.convolve(padded, np.ones(window * 2 + 1) / (window * 2 + 1), mode="same")[window:-window]
    threshold = local + (1.0 - max(0.0, min(1.0, sensitivity))) * 0.25

    found: list[float] = []
    minimum_gap = 0.18  # nothing musical is faster than about 330 bpm
    last = -minimum_gap
    for index, value in enumerate(rise):
        at = index * hop
        if value > threshold[index] and value > 0.08 and at - last >= minimum_gap:
            found.append(round(at, 3))
            last = at

    bpm = None
    if len(found) > 3:
        gaps = np.diff(found)
        # The mode of the gaps, to a fiftieth of a second, rather than the mean.
        counts: dict[float, int] = {}
        for gap in gaps:
            key = round(float(gap) * 50) / 50
            counts[key] = counts.get(key, 0) + 1
        common = max(counts, key=lambda k: counts[k])
        if common > 0:
            bpm = round(60.0 / common, 1)

    return {"beats": found, "bpm": bpm, "count": len(found)}


def ducking(
    speech: np.ndarray,
    rate: int = RATE,
    *,
    depth: float = 0.25,
    attack: float = 0.15,
    release: float = 0.4,
    threshold: float = 0.02,
) -> dict:
    """The envelope music should follow under this speech.

    Returned as keyframes rather than as processed audio, so a person can see
    where the music was pulled down, move a point, or throw one away. `depth` is
    what the music drops to, attack and release are how long it takes to get
    there and back.
    """
    level, hop = _envelope(speech, rate)
    if len(level) == 0:
        return {"keyframes": [], "regions": []}

    speaking = level > threshold
    # Close gaps shorter than the release, so a breath between words does not
    # let the music jump back up and down again.
    gap_frames = max(1, int(release / hop))
    filled = speaking.copy()
    run = 0
    for index, value in enumerate(speaking):
        if value:
            if 0 < run <= gap_frames:
                filled[index - run : index] = True
            run = 0
        else:
            run += 1

    regions: list[tuple[float, float]] = []
    start = None
    for index, value in enumerate(filled):
        if value and start is None:
            start = index * hop
        elif not value and start is not None:
            regions.append((start, index * hop))
            start = None
    if start is not None:
        regions.append((start, len(filled) * hop))

    # Anything shorter than the attack is not speech worth ducking for.
    regions = [(a, b) for a, b in regions if b - a > attack]

    depth = max(0.0, min(1.0, depth))
    keyframes: list[dict] = []
    for begin, end in regions:
        keyframes.append({"t": round(max(0.0, begin - attack), 3), "props": {"volume": 1.0}})
        keyframes.append({"t": round(begin, 3), "props": {"volume": depth}})
        keyframes.append({"t": round(end, 3), "props": {"volume": depth}})
        keyframes.append({"t": round(end + release, 3), "props": {"volume": 1.0}})

    return {
        "keyframes": keyframes,
        "regions": [{"start": round(a, 3), "duration": round(b - a, 3)} for a, b in regions],
        "depth": depth,
    }
