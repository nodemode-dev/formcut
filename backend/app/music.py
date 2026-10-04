"""The music's grid: tempo, beats, bars, the final hit, and joins a whole number of bars apart.

From the owner's Posh cutdowns: media.beats read the 125 BPM master as 250 (the commonest gap between loudness rises
is an eighth note), and the joins that worked were a whole number of bars apart, in pauses between sentences. Here:
spectral flux as the onset curve; tempo by autocorrelation weighted towards 120 BPM, then tempo and phase searched
together in 0.01 BPM steps for the grid whose beats carry the most onset strength. On the Posh mix: 124.97 BPM, a
1.9205 s bar, the first beat at 0.12 s (the report: 125, 1.92, 0.13); every delivered join a whole number of bars
apart to 13 ms; the final hit 69.257 s (69.25). The downbeat is not found from the audio (a four-on-the-floor kick
gives beat one no accent): the music's first beat stands for it, and says so.
"""

import subprocess
from pathlib import Path

import numpy as np

from .paths import DATA_DIR

CACHE = DATA_DIR / "music"
RATE, HOP, WINDOW = 22050, 220, 2048
STEP = HOP / RATE  # about 10 ms between onset values


def _audio(path: Path) -> np.ndarray:
    command = ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(command, capture_output=True, check=False).stdout, np.float32)


def onset_curve(samples: np.ndarray) -> np.ndarray:
    """Spectral flux: the new energy appearing across frequencies each 10 ms, its slow drift taken off."""
    padded = np.pad(samples, (WINDOW // 2, WINDOW // 2))
    frames = np.lib.stride_tricks.sliding_window_view(padded, WINDOW)[::HOP] * np.hanning(WINDOW)
    magnitude = np.log1p(100 * np.abs(np.fft.rfft(frames, axis=1)))
    flux = np.maximum(0, np.diff(magnitude, axis=0, prepend=magnitude[:1])).sum(1)
    flux -= np.convolve(flux, np.ones(50) / 50, mode="same")
    return np.maximum(flux, 0)


def beat_grid(flux: np.ndarray) -> tuple[float, float]:
    """(bpm, first beat in seconds): a coarse tempo from the autocorrelation weighted towards 120 BPM, then tempo
    within 1.5 BPM of it and phase searched together for the grid whose beats carry the most onset strength."""
    lags = np.arange(int(60 / 200 / STEP), int(60 / 50 / STEP) + 1)
    correlation = np.array([np.dot(flux[:-lag], flux[lag:]) / (len(flux) - lag) for lag in lags])
    tempi = 60 / (lags * STEP)
    coarse = float(tempi[np.argmax(correlation * np.exp(-0.5 * (np.log2(tempi / 120) / 0.9) ** 2))])
    best = (-1.0, coarse, 0.0)
    for bpm in np.arange(coarse - 1.5, coarse + 1.5, 0.01):
        period = 60 / bpm
        phases = np.arange(0, period, STEP)
        beats = np.arange(int(len(flux) * STEP / period))
        where = np.round((phases[:, None] + beats[None, :] * period) / STEP).astype(int)
        scores = np.where(where < len(flux), flux[np.minimum(where, len(flux) - 1)], 0).sum(1)
        k = int(np.argmax(scores))
        if scores[k] > best[0]:
            best = (float(scores[k]), float(bpm), float(phases[k]))
    return round(best[1], 2), round(best[2], 3)


def final_hit(samples: np.ndarray, flux: np.ndarray, bpm: float, first: float) -> float | None:
    """The last strong onset (top tenth) after which the sound decays to half within three seconds, snapped to the
    nearest beat: the chord a spot can end on."""
    energy = np.sqrt(np.convolve(samples.astype(np.float64) ** 2, np.ones(2205) / 2205, mode="same"))[::HOP][: len(flux)]
    peaks = [i for i in range(1, len(flux) - 1) if flux[i] >= flux[i - 1] and flux[i] > flux[i + 1]]
    if not peaks:
        return None
    floor = np.percentile(flux[peaks], 90)

    def decays(i: int) -> bool:
        after = energy[i + 20 : i + 300]
        return len(after) > 50 and after[-1] < 0.5 * after[:20].max()

    ending = [i for i in peaks if flux[i] > floor and decays(i)]
    if not ending:
        return None
    period = 60 / bpm
    at = ending[-1] * STEP
    return round(first + round((at - first) / period) * period, 3)


def music_map(media_id: str, path: Path) -> dict:
    """A media's tempo, beat, bar, first beat and final hit, measured once and kept."""
    import json

    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{media_id}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    samples = _audio(path)
    flux = onset_curve(samples)
    bpm, first = beat_grid(flux)
    found = {
        "bpm": bpm,
        "beat": round(60 / bpm, 5),
        "bar": round(4 * 60 / bpm, 5),
        "first_beat": first,
        "downbeat": first,
        "downbeat_basis": "the music's first beat (beat one carries no accent this measure can find)",
        "final_hit": final_hit(samples, flux, bpm, first),
        "duration": round(len(samples) / RATE, 3),
    }
    cached.write_text(json.dumps(found))
    return found


def safe_zones(probabilities: np.ndarray, step: float) -> list[list[float]]:
    """Stretches where a cut does not go through speech (the speech check's rule, at the voice map's step)."""
    from .speech import through_speech

    zones, start = [], None
    for i in range(len(probabilities) + 1):
        ok = i < len(probabilities) and not through_speech(probabilities, i * step)
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            zones.append([round(start * step, 3), round((i - 1) * step, 3)])
            start = None
    return zones


def joins(zones: list[list[float]], bar: float, out_from: float = 0.0, out_to: float = 1e9, tolerance: float = 0.03) -> list[dict]:
    """Joins a whole number of bars apart: an out-point in one safe zone and an in-point in a later one, the distance
    k bars within the tolerance. Each with the out and in nearest the zones' middles that keep the distance exact."""
    found = []
    for a0, a1 in zones:
        if a1 < out_from or a0 > out_to:
            continue
        for b0, b1 in zones:
            if b0 <= a1:
                continue
            for k in range(max(1, int((b0 - a1) // bar)), int((b1 - a0) // bar) + 2):
                span = k * bar
                lowest, highest = max(a0, b0 - span), min(a1, b1 - span)  # out-points keeping both ends in their zones
                if lowest <= highest + tolerance:
                    out = (lowest + highest) / 2
                    found.append({"out": round(out, 3), "in": round(out + span, 3), "bars": k, "out_zone": [a0, a1], "in_zone": [b0, b1]})
    return found
