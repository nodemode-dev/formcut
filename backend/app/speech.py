"""Speech-safe cuts: where someone is speaking, and which edit points cut through them.

From the owner's Posh cutdowns: round one cut the receptionist's line at 11.18 s, but "calling" runs 11.18 to 11.42;
a 40 ms dip before it (the closure of the c) looked like a pause. Transcription word times cannot place cuts (formcut's
own put "calling" a second early), and loudness pauses fail under a music bed (the groove's arrival and the end
card's ringing chord read as not quiet). The question is whether someone is speaking: Silero VAD (MIT, ONNX) gives a
speech probability every 32 ms, music or not. A cut is unsafe when speech is on both sides of it within 100 ms (mean
probability above 0.5); on the Posh mix that accepts all 21 cut points of the seven delivered spots and refuses
11.18 (0.99 either side).
"""

import subprocess
from pathlib import Path

import numpy as np

from .paths import DATA_DIR

CACHE = DATA_DIR / "speech"
RATE = 16000
CHUNK = 512  # Silero VAD's window at 16 kHz
STEP = CHUNK / RATE  # 32 ms between probabilities


def _audio(path: Path) -> np.ndarray:
    command = ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(command, capture_output=True, check=False).stdout, np.float32)


def voice_probabilities(path: Path, report=None, cancelled=None) -> np.ndarray:
    """Silero VAD's speech probability for each 32 ms of a file's first audio stream."""
    import onnxruntime as ort

    from .model_manager import model_file, ready

    if not ready("voice-activity"):
        raise RuntimeError("the voice-activity model is not downloaded: Settings, Models, or POST /api/models/voice-activity/download")
    session = ort.InferenceSession(str(model_file("silero_vad.onnx")), providers=["CPUExecutionProvider"])
    samples = _audio(path)
    state, context, out = np.zeros((2, 1, 128), np.float32), np.zeros(64, np.float32), []
    total = max(1, len(samples) // CHUNK)
    for n, start in enumerate(range(0, len(samples) - CHUNK + 1, CHUNK)):
        if cancelled and cancelled():
            raise InterruptedError
        window = samples[start : start + CHUNK]
        chunk = np.concatenate([context, window])[None, :].astype(np.float32)
        probability, state = session.run(None, {"input": chunk, "state": state, "sr": np.array(RATE, np.int64)})
        out.append(float(probability[0][0]))
        context = window[-64:]
        if report and n % 200 == 0:
            report(n / total, f"{n * STEP:.0f} s of {total * STEP:.0f} s")
    return np.array(out, np.float32)


def voice_map(media_id: str, path: Path, report=None, cancelled=None) -> np.ndarray:
    """A media's speech probabilities, measured once and kept."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"{media_id}.npy"
    if cached.exists():
        return np.load(cached)
    probabilities = voice_probabilities(path, report, cancelled)
    np.save(cached, probabilities)
    return probabilities


def _mean(probabilities: np.ndarray, start: float, end: float) -> float:
    first, last = int(max(0.0, start) / STEP), int(max(0.0, end) / STEP) + 1
    window = probabilities[first:last]
    return float(window.mean()) if len(window) else 0.0


def through_speech(probabilities: np.ndarray, time: float, reach: float = 0.10) -> bool:
    """A cut at time goes through speech: someone is speaking on both sides of it within reach."""
    return min(_mean(probabilities, time - reach, time), _mean(probabilities, time, time + reach)) > 0.5


def pauses(probabilities: np.ndarray, shortest: float = 0.15) -> list[list[float]]:
    """Stretches of shortest seconds or more where no one speaks (probability under 0.5)."""
    quiet, found, start = probabilities < 0.5, [], None
    for i, still in enumerate(np.append(quiet, False)):
        if still and start is None:
            start = i
        elif not still and start is not None:
            if (i - start) * STEP >= shortest:
                found.append([round(start * STEP, 3), round(i * STEP, 3)])
            start = None
    return found


def check_cuts(probabilities: np.ndarray, times: list[float]) -> list[dict]:
    """Each edit point: safe or not, the speech either side, and the nearest pause to move it into when unsafe."""
    quiet = pauses(probabilities)
    out = []
    for time in times:
        row = {
            "time": round(time, 3),
            "speech_before": round(_mean(probabilities, time - 0.10, time), 2),
            "speech_after": round(_mean(probabilities, time, time + 0.10), 2),
            "safe": not through_speech(probabilities, time),
        }
        if not row["safe"] and quiet:
            start, end = min(quiet, key=lambda span: min(abs(span[0] - time), abs(span[1] - time)))
            row["nearest_pause"] = [start, end]
        out.append(row)
    return out


REACH = 0.6
PAD = 0.06


def loudness_activity(path: Path, start: float, end: float) -> np.ndarray:
    """Speech-like activity from loudness alone, 32 ms per value from start, for when the voice-activity model is not downloaded."""
    command = ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, start):.3f}", "-t", f"{max(0.1, end - start):.3f}", "-i", str(path)]
    command += ["-map", "0:a:0", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "-"]
    samples = np.frombuffer(subprocess.run(command, capture_output=True, check=False).stdout, np.float32)
    frames = len(samples) // CHUNK
    if frames == 0:
        return np.zeros(0, np.float32)
    rms = np.sqrt(np.mean(samples[: frames * CHUNK].reshape(frames, CHUNK) ** 2, axis=1)) + 1e-9
    level = 20 * np.log10(rms)
    floor = float(np.percentile(level, 20))
    return np.clip((level - floor - 5) / 10, 0, 1).astype(np.float32)


def _edge(activity: np.ndarray, offset: float, near: float, onset: bool) -> float | None:
    speaking = activity >= 0.5
    first = max(1, int((near - REACH - offset) / STEP))
    last = min(len(activity) - 1, int((near + REACH - offset) / STEP))
    if last < first:
        return None
    turns = [i for i in range(first, last + 1) if speaking[i] != speaking[i - 1] and bool(speaking[i]) == onset]
    best = min(turns, key=lambda i: abs(offset + i * STEP - near)) if turns else first + int(np.argmin(activity[first : last + 1]))
    return offset + best * STEP


def speech_range(media_id: str, path: Path, start: float, end: float) -> dict | None:
    """The span someone speaks in near start and end, in source seconds: from the speech onset to the speech offset, each found in the audio."""
    from .model_manager import ready

    if ready("voice-activity"):
        activity, offset, source = voice_map(media_id, path), 0.0, "voice"
    else:
        offset = max(0.0, start - REACH - 0.2)
        activity, source = loudness_activity(path, offset, end + REACH + 0.2), "loudness"
    begin, finish = _edge(activity, offset, start, True), _edge(activity, offset, end, False)
    if begin is None or finish is None:
        return None
    begin, finish = max(0.0, begin - PAD), finish + PAD
    if finish - begin <= 0.05:
        return None
    return {"start": round(begin, 3), "end": round(finish, 3), "source": source}
