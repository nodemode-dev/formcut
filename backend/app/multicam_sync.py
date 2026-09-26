"""Multicam sync by sound.

Angles are cameras that ran at the same time; their sound is the same event
from different places. The first track of a multicam timeline is the
reference; every other track's clips are decoded to a loudness envelope
(rhythm._envelope, ten milliseconds a step), cross-correlated against the
reference's envelope with both sides mean-removed and normalised, and the lag
with the best match is the offset the track needs. The tracks are shifted by
that offset so their sound, and so their pictures, line up, which is the step
before the compound is placed on the cut timeline. A track whose match is
weak (below the confidence floor) is reported and left where it is.
"""

import subprocess

import numpy as np

from .media import MEDIA_DIR
from .rhythm import RATE, _envelope

HOP = 0.01
MAX_LAG = 8.0  # the fine search, seconds either way; the coarse pass first covers COARSE_LAG
COARSE_LAG = 120.0  # a camera started two minutes late is still found
COARSE_HOP = 0.1
CONFIDENCE = 0.25


def _track_samples(track: dict, seconds: float) -> np.ndarray | None:
    """The track's sound over the first `seconds` of the timeline, mono at RATE, clips laid at their starts."""
    out = np.zeros(int(seconds * RATE), np.float32)
    found = False
    for clip in track.get("clips") or []:
        if clip.get("kind") not in ("video", "audio") or not clip.get("mediaId") or clip.get("muted"):
            continue
        path = next(iter(MEDIA_DIR.glob(f"{clip['mediaId']}.*")), None)
        if path is None:
            continue
        span = min(float(clip["duration"]), max(0.0, seconds - float(clip["start"])))
        if span <= 0:
            continue
        run = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-ss",
                str(float(clip.get("sourceIn", 0))),
                "-t",
                str(span),
                "-i",
                str(path),
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(RATE),
                "-f",
                "f32le",
                "pipe:1",
            ],
            capture_output=True,
            check=False,
        )
        if run.returncode or not run.stdout:
            continue
        samples = np.frombuffer(run.stdout, np.float32)
        at = int(float(clip["start"]) * RATE)
        take = min(len(samples), len(out) - at)
        if take > 0:
            out[at : at + take] += samples[:take]
            found = True
    return out if found else None


def best_lag(
    reference: np.ndarray, other: np.ndarray, hop: float = HOP, max_lag: float = MAX_LAG, centre: float = 0.0
) -> tuple[float, float]:
    """The lag (seconds, positive when `other` runs late) with the best normalised match, and that match in 0..1;
    the search runs `max_lag` either way around `centre`."""
    a = reference - reference.mean()
    b = other - other.mean()
    if not len(a) or not len(b) or not a.std() or not b.std():
        return 0.0, 0.0
    a = a / (a.std() * len(a))
    b = b / b.std()
    n = len(a) + len(b) - 1
    size = 1 << (n - 1).bit_length()
    corr = np.fft.irfft(np.fft.rfft(a, size) * np.conj(np.fft.rfft(b, size)), size)
    # corr[k] pairs a[i] with b[i - k]; lag k means `other` sits k steps late
    limit = int(max_lag / hop)
    middle = round(-centre / hop)  # the correlation's index runs the other way from the promised sign
    lags = np.arange(middle - limit, middle + limit + 1)
    values = corr[np.mod(lags, size)]
    # Music and speech repeat, so a periodic signal can match itself one
    # period away nearly as well as at the true lag. Among peaks within a few
    # percent of the best, the smallest lag wins: cameras were started
    # within moments of each other, not a chorus apart.
    top = float(values.max())
    near = np.flatnonzero(values >= top * 0.97)
    best = int(near[np.argmin(np.abs(lags[near]))])
    # The correlation's index runs the other way from the convention promised
    # above; the synthetic proof (one angle 1.37 s late) fixed the sign.
    return float(-lags[best] * hop), float(max(0.0, min(1.0, values[best])))


def sync_tracks(timeline: dict, seconds: float = 120.0) -> list[dict]:
    """Shift every track after the first so its sound lines up with the first's; the offsets and matches come back."""
    tracks = timeline.get("tracks") or []
    if len(tracks) < 2:
        return []
    reference = _track_samples(tracks[0], seconds)
    if reference is None:
        raise ValueError("The first track, the reference angle, has no sound to line up against")
    ref_env, hop = _envelope(reference, RATE, HOP)
    lags = {0: 0.0}
    report = []
    for index, track in enumerate(tracks[1:], start=1):
        samples = _track_samples(track, seconds)
        if samples is None:
            report.append(
                {"track": index, "name": track.get("name", ""), "offset": 0.0, "match": 0.0, "applied": False, "reason": "no sound"}
            )
            continue
        env, _ = _envelope(samples, RATE, HOP)
        # Two stages: a coarse pass on a ten-times-hopped envelope over two
        # minutes either way finds the neighbourhood, and the fine pass
        # searches eight seconds around it at ten milliseconds, so a camera
        # started late is found without a manual trim and the fine result
        # keeps its precision.
        coarse_ref, coarse_hop = _envelope(reference, RATE, COARSE_HOP)
        coarse_env, _ = _envelope(samples, RATE, COARSE_HOP)
        coarse, _match = best_lag(coarse_ref, coarse_env, coarse_hop, COARSE_LAG)
        lag, match = best_lag(ref_env, env, hop, MAX_LAG, centre=coarse)
        applied = match >= CONFIDENCE and abs(lag) >= hop / 2
        if applied:
            lags[index] = lag
        report.append(
            {
                "track": index,
                "name": track.get("name", ""),
                "offset": round(-lag, 3),
                "match": round(match, 3),
                "applied": applied,
                "reason": None if applied else ("weak match" if match < CONFIDENCE else "already aligned"),
            }
        )
    # A track whose sound runs `lag` late has its clips moved `lag` earlier.
    # Nothing may start before zero, so every track (the reference too) moves
    # later by the largest lag, which keeps the alignment and the first frame.
    lift = max(lags.values())
    for index, lag in lags.items():
        shift = lift - lag
        if abs(shift) < hop / 2:
            continue
        for clip in tracks[index].get("clips") or []:
            clip["start"] = round(max(0.0, float(clip["start"]) + shift) * 100) / 100
    return report
