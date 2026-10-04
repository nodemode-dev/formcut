"""A delivery check for a rendered file, machine-readable so an agent can gate delivery on it.

From the owner's Posh cutdowns: repeated frames were invisible in the edit and only showed when the rendered files
were measured (35 to 40% of frames flagged in round two), and every QC step ran outside formcut. This measures the
deliverable: its length, frame count and rate; exact repeats (identical frame hashes) and perceptual repeats
(ffmpeg's mpdecimate, the measure that session used); freezes; black and flash frames; how sharp the first and last
frames are against the rest; loudness and true peak; and clicks at audio edit points. `passed` is false with the
reasons whenever a rule fails.
"""

import json
import subprocess
from pathlib import Path

import cv2
import numpy as np


def _ffmpeg(args: list[str]) -> str:
    return subprocess.run(["ffmpeg", "-nostats", "-hide_banner", *args], capture_output=True, text=True, check=False).stderr


def _probe(path: Path) -> dict:
    fields = ["-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,bit_rate", "-show_entries", "format=duration"]
    run = subprocess.run(["ffprobe", "-v", "error", *fields, "-of", "json", str(path)], capture_output=True, text=True, check=False)
    return json.loads(run.stdout or "{}")


def _exact_repeats(path: Path) -> list[int]:
    """Frames identical to the one before (by hash of the decoded picture)."""
    command = ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:v:0", "-f", "framemd5", "-"]
    run = subprocess.run(command, capture_output=True, text=True, check=False)
    hashes = [line.rsplit(",", 1)[-1].strip() for line in run.stdout.splitlines() if line and not line.startswith("#")]
    return [i for i in range(1, len(hashes)) if hashes[i] == hashes[i - 1]]


def _perceptual_repeats(path: Path, fps: float, frames: int) -> list[int]:
    """Frames mpdecimate drops as near duplicates of the frame kept before them: the frames it keeps are named by
    their timestamps (showinfo after it numbers only what it kept), every other frame is flagged."""
    log = _ffmpeg(["-i", str(path), "-map", "0:v:0", "-vf", "mpdecimate,showinfo", "-f", "null", "-"])
    times = [float(line.split("pts_time:")[1].split()[0]) for line in log.splitlines() if "showinfo" in line and "pts_time:" in line]
    if not times or frames <= 0 or fps <= 0:
        return []
    kept = {round(t * fps) for t in times}
    return [i for i in range(frames) if i not in kept]


def _spans(log: str, start_key: str, end_key: str) -> list[list[float]]:
    starts = [float(line.split(start_key)[1].split()[0]) for line in log.splitlines() if start_key in line]
    ends = [float(line.split(end_key)[1].split()[0]) for line in log.splitlines() if end_key in line]
    return [[round(a, 3), round(b, 3)] for a, b in zip(starts, ends, strict=False)]


def _pictures(path: Path) -> tuple[list[float], list[float]]:
    """Per frame, at a quarter of the size: mean brightness, and sharpness (variance of the Laplacian)."""
    capture, means, sharp = cv2.VideoCapture(str(path)), [], []
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        small = cv2.cvtColor(cv2.resize(frame, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        means.append(float(small.mean()))
        sharp.append(float(cv2.Laplacian(small, cv2.CV_32F).var()))
    capture.release()
    return means, sharp


def _clicks(path: Path, edits: list[float]) -> list[dict]:
    """At each audio edit, a click: the high-passed level within 15 ms of the edit far above the level around it."""
    command = ["ffmpeg", "-v", "error", "-i", str(path), "-map", "0:a:0", "-ac", "1", "-ar", "48000", "-f", "f32le", "-"]
    run = subprocess.run(command, capture_output=True, check=False)
    audio = np.frombuffer(run.stdout, np.float32)
    if audio.size < 4800:
        return []
    high = np.abs(np.diff(audio))  # a first difference: the click's sudden step, little of the music's body
    found = []
    for at in edits:
        centre = int(at * 48000)
        near = high[max(0, centre - 720) : centre + 720]
        around = np.concatenate([high[max(0, centre - 9600) : max(0, centre - 1440)], high[centre + 1440 : centre + 9600]])
        if near.size and around.size:
            ratio = float(near.max() / max(1e-9, np.percentile(around, 99.5)))
            if ratio > 2.5:
                found.append({"at": round(at, 3), "ratio": round(ratio, 2)})
    return found


def quality_report(
    path: Path, edits: list[float] | None = None, loudness_target: float | None = None, true_peak_ceiling: float = -1.0
) -> dict:
    """The delivery check of a rendered file. edits: audio edit points in seconds, for the click check."""
    from .render_api import measure_loudness

    probe = _probe(path)
    video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    audio = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), {})
    num, _, den = str(video.get("r_frame_rate", "0/1")).partition("/")
    fps = float(num) / max(1.0, float(den or 1))
    means, sharp = _pictures(path)
    frames = len(means)
    exact = _exact_repeats(path)
    perceptual = _perceptual_repeats(path, fps, frames)
    freeze_log = _ffmpeg(["-i", str(path), "-map", "0:v:0", "-vf", "freezedetect=n=-60dB:d=0.5", "-f", "null", "-"])
    black_log = _ffmpeg(["-i", str(path), "-map", "0:v:0", "-vf", "blackdetect=d=0.04:pix_th=0.10", "-f", "null", "-"])
    flashes = [i for i in range(1, frames - 1) if means[i] - max(means[i - 1], means[i + 1]) > 40]
    # against the frames next to them in their own shot, not the spot's median: a plain opening shot is not a soft
    # one (the Posh :15 More Than Answering opens on its shot's sharpest frame, below the spot's median detail)
    opening = float(np.median(sharp[1:7])) if len(sharp) > 7 else 0.0
    closing = float(np.median(sharp[-7:-1])) if len(sharp) > 7 else 0.0
    first_sharp = sharp[0] / opening if opening else 1.0
    last_sharp = sharp[-1] / closing if closing else 1.0
    loud = measure_loudness(path) if audio else None
    report = {
        "file": str(path),
        "duration": round(float(probe.get("format", {}).get("duration") or 0), 3),
        "frames": frames,
        "fps": round(fps, 3),
        "size": [video.get("width"), video.get("height")],
        "video_codec": video.get("codec_name"),
        "audio_codec": audio.get("codec_name"),
        "audio_kbps": round(int(audio.get("bit_rate") or 0) / 1000) if audio else None,
        "exact_repeats": {"count": len(exact), "frames": exact[:50]},
        "perceptual_repeats": {"count": len(perceptual), "frames": perceptual[:50]},
        "freezes": _spans(freeze_log, "freeze_start: ", "freeze_end: "),
        "black": _spans(black_log, "black_start:", "black_end:"),
        "flash_frames": flashes[:50],
        "first_frame_sharpness": round(first_sharp, 2),
        "last_frame_sharpness": round(last_sharp, 2),
        "loudness": loud,
        "clicks": _clicks(path, edits) if (audio and edits) else None,
    }
    reasons = []
    if exact:
        reasons.append(f"{len(exact)} frames repeat the one before exactly")
    if perceptual:
        reasons.append(f"{len(perceptual)} frames are near duplicates (mpdecimate)")
    if report["freezes"]:
        reasons.append(f"{len(report['freezes'])} freezes of half a second or more")
    if report["black"]:
        reasons.append("black frames")
    if flashes:
        reasons.append(f"{len(flashes)} flash frames")
    if first_sharp < 0.5:
        reasons.append("the first frame is soft against the rest")
    if last_sharp < 0.5:
        reasons.append("the last frame is soft against the rest")
    if loud and loud["true_peak"] > true_peak_ceiling:
        reasons.append(f"true peak {loud['true_peak']} dBTP over the {true_peak_ceiling} ceiling")
    if loud and loudness_target is not None and abs(loud["integrated"] - loudness_target) > 1.0:
        reasons.append(f"loudness {loud['integrated']} LUFS, more than 1 LU from the {loudness_target} target")
    if report["clicks"]:
        reasons.append(f"{len(report['clicks'])} clicks at edits")
    report["passed"] = not reasons
    report["reasons"] = reasons
    return report
