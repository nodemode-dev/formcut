import atexit
import math
import os
import subprocess
import tempfile
import threading
import time
from fractions import Fraction

import numpy as np

from .media import _ffprobe


class VideoSource:
    def __init__(self, path, limit=None):
        self.path = str(path)
        metadata = _ffprobe(path)
        stream = next((item for item in metadata.get("streams", []) if item.get("codec_type") == "video"), None)
        if stream is None:
            raise ValueError("This media has no video stream")
        self.width, self.height = int(stream["width"]), int(stream["height"])
        rotation = float(stream.get("tags", {}).get("rotate", 0))
        for item in stream.get("side_data_list", []):
            if "rotation" in item:
                rotation = float(item["rotation"])
        if round(rotation / 90) % 2:
            self.width, self.height = self.height, self.width
        if limit and max(self.width, self.height) > limit:
            ratio = limit / max(self.width, self.height)
            self.width, self.height = max(2, round(self.width * ratio / 2) * 2), max(2, round(self.height * ratio / 2) * 2)
        try:
            self.fps = float(Fraction(stream.get("avg_frame_rate") or "30/1"))
        except (ValueError, ZeroDivisionError):
            self.fps = 30.0
        if self.fps <= 0:
            self.fps = 30.0
        duration = float(stream.get("duration") or metadata.get("format", {}).get("duration") or 0)
        self.frame_count = max(0, math.ceil(duration * self.fps))
        self.position = 0
        self.requested = 0
        self.process = None
        self.errors = None
        self.key = (self.path, limit)
        self.last = None

    def seek(self, frame):
        self.requested = max(0, int(frame))

    def _start(self):
        self.release()
        self.position = self.requested
        self.errors = tempfile.TemporaryFile()
        self.process = subprocess.Popen(
            [
                "ffmpeg",
                "-v",
                "error",
                "-nostdin",
                "-threads",
                "0",
                *hwaccel_flags(),
                "-ss",
                str(self.position / self.fps),
                "-i",
                self.path,
                "-map",
                "0:v:0",
                "-an",
                "-sn",
                "-dn",
                "-vf",
                f"fps={self.fps},scale={self.width}:{self.height}",
                "-threads",
                "1",
                "-pix_fmt",
                "bgr24",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=self.errors,
        )

    def read(self):
        if self.frame_count and self.requested >= self.frame_count:
            return False, None
        if self.last is not None and self.requested == self.last[0]:
            self.requested = self.position
            return True, self.last[1]
        gap = self.requested - self.position
        if self.process is None or gap < 0 or gap > max(1, round(self.fps * 2)):
            self._start()
        size = self.width * self.height * 3
        # One buffer per frame returned, filled in place. Reading chunks into new
        # bytes objects and appending them copied every byte twice, and the array
        # then copied it a third time, though no buffer is ever reused: 16 ms a
        # frame for a 1080p picture in picture, of the engine's 41.
        pieces = bytearray(size)
        view = memoryview(pieces)
        while True:
            filled = 0
            while filled < size:
                count = self.process.stdout.readinto(view[filled:])
                if not count:
                    view.release()
                    self.release()
                    return False, None
                filled += count
            self.position += 1
            if self.position > self.requested:
                break
        view.release()
        self.requested = self.position
        frame = np.frombuffer(pieces, np.uint8).reshape(self.height, self.width, 3)
        if self.key[1]:
            self.last = (self.position - 1, frame)
        return True, frame

    def release(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait()
            self.process.stdout.close()
            self.process = None
        if self.errors is not None:
            self.errors.close()
            self.errors = None


_pool_lock = threading.Lock()
_idle: list[tuple[float, VideoSource]] = []
IDLE_LIMIT = 4
IDLE_SECONDS = 60.0


_HWACCEL: list[str] | None = None


def hwaccel_flags() -> list[str]:
    """Hardware decode when a method actually decodes here, else nothing.

    Probed once, by decoding a generated clip rather than trusting `-hwaccels`,
    which lists methods a machine merely has drivers for: this container lists
    cuda with no GPU behind it. Any failure leaves the software path exactly as
    it was, so a machine without a decoder never pays for the attempt.
    """
    global _HWACCEL
    if _HWACCEL is None:
        _HWACCEL = []
        if os.environ.get("FORMCUT_HWACCEL") == "off":
            return _HWACCEL
        try:
            listed = subprocess.run(["ffmpeg", "-v", "error", "-hwaccels"], capture_output=True, text=True, check=False, timeout=20).stdout
            names = {line.strip() for line in listed.splitlines()[1:] if line.strip()}
            for candidate in ("videotoolbox", "cuda", "qsv", "vaapi", "d3d11va"):
                if candidate not in names:
                    continue
                probe = subprocess.run(
                    [
                        "ffmpeg",
                        "-v",
                        "error",
                        "-hwaccel",
                        candidate,
                        "-f",
                        "lavfi",
                        "-i",
                        "testsrc2=size=320x240:rate=30:duration=0.2",
                        "-frames:v",
                        "3",
                        "-f",
                        "null",
                        "-",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
                if probe.returncode == 0 and not probe.stderr.strip():
                    _HWACCEL = ["-hwaccel", candidate]
                    break
        except Exception:
            _HWACCEL = []
    return _HWACCEL


def acquire(path, limit=None, at=None) -> VideoSource:
    key = (str(path), limit)
    now = time.monotonic()
    with _pool_lock:
        stale = [entry for entry in _idle if now - entry[0] > IDLE_SECONDS]
        for entry in stale:
            _idle.remove(entry)
        candidates = [entry for entry in _idle if entry[1].key == key] if limit else []
        usable = [entry for entry in candidates if at is not None and entry[1].position - 1 <= int(at * entry[1].fps + 1e-7)]
        match = max(usable, key=lambda entry: entry[1].position) if usable else (candidates[-1] if candidates else None)
        if match:
            _idle.remove(match)
    for _, source in stale:
        source.release()
    return match[1] if match else VideoSource(path, limit)


def recycle(source: VideoSource) -> None:
    if not source.key[1] or source.process is None:
        source.release()
        return
    with _pool_lock:
        _idle.append((time.monotonic(), source))
        surplus = _idle[:-IDLE_LIMIT]
        del _idle[:-IDLE_LIMIT]
    for _, extra in surplus:
        extra.release()


def drain() -> None:
    with _pool_lock:
        idle = list(_idle)
        _idle.clear()
    for _, source in idle:
        source.release()


atexit.register(drain)
