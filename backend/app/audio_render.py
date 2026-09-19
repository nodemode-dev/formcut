from .processes import communicate
import math
import subprocess
import wave

import numpy as np

from .catalogue import AUDIO_CHAINS
from .media import MEDIA_DIR, _ffprobe, reversed_path
from .render_document import flatten
from .timing import fade_at, source_delta

RATE = 48000


def time_stretch(samples: np.ndarray, clip: dict, count: int, cancelled=lambda: False) -> np.ndarray:
    if not clip.get("speedCurve") and abs(float(clip.get("speed", 1)) - 1) < 1e-8:
        return np.pad(samples[:count], ((0, max(0, count - len(samples))), (0, 0)))
    window_size, hop = 2048, 512
    window = np.hanning(window_size)
    padded = np.pad(samples, ((window_size // 2, window_size), (0, 0)))
    result = np.zeros((count + window_size * 2, 2), np.float64)
    weights = np.zeros(len(result), np.float64)
    phase_step = 2 * math.pi * np.arange(window_size // 2 + 1) * hop / window_size
    phase = None
    for frame in range(math.ceil(count / hop) + 1):
        if cancelled():
            raise InterruptedError("Cancelled")
        target = frame * hop
        source = source_delta(clip, target / RATE) * RATE / hop
        index = int(source)
        fraction = source - index
        first = padded[index * hop:index * hop + window_size]
        second = padded[(index + 1) * hop:(index + 1) * hop + window_size]
        if len(first) < window_size:
            break
        if len(second) < window_size:
            second = np.pad(second, ((0, window_size - len(second)), (0, 0)))
        a = np.fft.rfft(first * window[:, None], axis=0)
        b = np.fft.rfft(second * window[:, None], axis=0)
        if phase is None:
            phase = np.angle(a)
        magnitude = abs(a) * (1 - fraction) + abs(b) * fraction
        transformed = np.fft.irfft(magnitude * np.exp(1j * phase), axis=0)
        result[target:target + window_size] += transformed * window[:, None]
        weights[target:target + window_size] += window ** 2
        delta = np.angle(b) - np.angle(a) - phase_step[:, None]
        delta -= 2 * math.pi * np.round(delta / (2 * math.pi))
        phase += phase_step[:, None] + delta
    result /= np.maximum(weights[:, None], 1e-8)
    return result[window_size // 2:window_size // 2 + count].astype(np.float32)


def filter_audio(samples: np.ndarray, chain: str, cancelled=lambda: False) -> np.ndarray:
    process = subprocess.Popen(["ffmpeg", "-v", "error", "-f", "f32le", "-ar", str(RATE), "-ac", "2", "-i", "pipe:0", "-af", chain, "-f", "f32le", "-ar", str(RATE), "-ac", "2", "pipe:1"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = communicate(process, samples.astype("<f4").tobytes(), cancelled=cancelled)
    if process.returncode:
        raise ValueError(error.decode(errors="replace")[-1000:])
    return np.frombuffer(output, "<f4").reshape(-1, 2).copy()

def render_audio(project: dict, destination, cancelled=lambda: False):
    total = int(math.ceil(project["duration"] * RATE))
    mix = np.zeros((total, 2), np.float32)
    for clip in flatten(project):
        if cancelled():
            raise InterruptedError("Cancelled")
        if clip["kind"] not in ("video", "audio") or clip.get("muted") or not clip.get("mediaId"):
            continue
        if clip.get("reversed"):
            candidate = reversed_path(clip["mediaId"])
            if not candidate.is_file():
                raise ValueError("Reversed copy is not prepared yet")
            paths = [candidate]
        else:
            paths = list(MEDIA_DIR.glob(f"{clip['mediaId']}.*"))
        if not paths:
            raise ValueError("Audio media is missing")
        if not any(s.get("codec_type") == "audio" for s in _ffprobe(paths[0]).get("streams", [])):
            continue
        duration = clip["duration"] + clip.get("extendOut", 0)
        samples = processed_clip_audio(clip, paths[0], cancelled)
        count = min(len(samples), int(duration * RATE))
        envelope_times = np.linspace(0, duration, max(2, math.ceil(duration * 200)))
        envelope = np.array([fade_at(clip, t) for t in envelope_times])
        gain = np.interp(np.arange(count) / RATE, envelope_times, envelope)
        samples = samples[:count] * gain[:, None] * max(0, min(4, float(clip.get("volume", 1))))
        pan = max(-1, min(1, float(clip.get("pan", 0))))
        samples[:, 0] *= min(1, 1 - pan)
        samples[:, 1] *= min(1, 1 + pan)
        offset = int(round(clip["start"] * RATE))
        count = min(count, total - offset)
        if count > 0:
            mix[offset:offset + count] += samples[:count]
    with wave.open(str(destination), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(RATE)
        out.writeframes(np.round(np.clip(mix, -1, 1) * 32767).astype("<i2").tobytes())

def processed_clip_audio(clip: dict, path, cancelled=lambda: False) -> np.ndarray:
    """One clip's sound after speed and effects, before gain, fades and pan.

    R2 factors this out so the per-clip cache the interface mixes live and the
    exported mix come from the same code, which is what keeps the two within
    the parity gate; gain, fades and pan stay outside because the interface
    applies them as live Web Audio automation.
    """
    duration = clip["duration"] + clip.get("extendOut", 0)
    span = source_delta(clip, duration)
    process = subprocess.Popen(["ffmpeg", "-v", "error", "-ss", str(clip.get("sourceIn") or 0), "-i", str(path), "-t", str(span), "-vn", "-f", "f32le", "-ar", str(RATE), "-ac", "2", "pipe:1"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = communicate(process, cancelled=cancelled)
    if process.returncode:
        raise ValueError(error.decode(errors="replace")[-1000:])
    raw = np.frombuffer(output, "<f4").reshape(-1, 2)
    samples = time_stretch(raw, clip, int(duration * RATE), cancelled)
    effects = list(clip.get("audioEffects") or [])
    if clip.get("audioFx"):
        effects.insert(0, {"id": clip["audioFx"], "amount": 1})
    for effect in effects:
        if effect["id"] not in AUDIO_CHAINS:
            raise ValueError("Unknown audio processor")
        wet = filter_audio(samples, AUDIO_CHAINS[effect["id"]], cancelled)
        count = max(len(samples), len(wet))
        amount = max(0, min(1, float(effect.get("amount", 1))))
        samples = np.pad(samples, ((0, count - len(samples)), (0, 0))) * (1 - amount) + np.pad(wet, ((0, count - len(wet)), (0, 0))) * amount
    return samples


def clip_envelope(clip: dict, count: int) -> np.ndarray:
    """The fade and volume curve the export applies; the interface mirrors it."""
    duration = clip["duration"] + clip.get("extendOut", 0)
    times = np.linspace(0, duration, max(2, math.ceil(duration * 200)))
    envelope = np.array([fade_at(clip, t) for t in times])
    gain = np.interp(np.arange(count) / RATE, times, envelope)
    return gain * max(0, min(4, float(clip.get("volume", 1))))
