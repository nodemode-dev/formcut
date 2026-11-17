import atexit
import contextlib
import math
import os
import re
import subprocess
import sys
import tempfile
import threading

try:
    import av
except ImportError:  # the pipe remains the decoder where PyAV is not installed
    av = None
import time
from fractions import Fraction

import numpy as np

from .media import _ffprobe

# The working space is BT.709. PQ and HLG sources are tone-mapped (X7); an
# SDR source tagged with other primaries (BT.2020 wide gamut, or a BT.601 SD
# tag) is converted here so its colours land where the grade, the LUTs and
# the encoder expect them: swscale applies a source's matrix when it makes
# RGB but never converts primaries, which is where a wide-gamut file goes
# wrong. An untagged source is left to swscale's rule, BT.601 for SD sizes.
PRIMARIES = ("bt709", "bt2020", "smpte431", "smpte432", "bt470m", "bt470bg", "smpte170m", "smpte240m", "film")
MATRICES = ("bt709", "bt2020nc", "bt2020c", "bt470bg", "smpte170m", "smpte240m", "fcc")
TRANSFERS = ("bt709", "smpte170m", "bt470bg", "bt470m", "iec61966-2-1", "bt2020-10", "bt2020-12", "smpte240m", "linear")


def _once(text: str, _said: set = set()) -> None:  # noqa: B006 - said once per run, on purpose
    if text not in _said:
        _said.add(text)
        with contextlib.suppress(OSError, ValueError, AttributeError):
            print(f"formcut: {text}", file=sys.__stderr__)


def bit_depth(stream: dict) -> int:
    """The bits a sample of the stream's pixel format carries (8 when the probe does not say)."""
    name = str(stream.get("pix_fmt") or "")
    if av is not None and name:
        try:
            return max(component.bits for component in av.VideoFormat(name).components)
        except (ValueError, TypeError):
            pass
    found = re.search(r"p(9|10|12|14|16)(le|be)?$|^p0(10|12|16)", name)
    if found:
        return int(found.group(1) or found.group(3))
    raw = str(stream.get("bits_per_raw_sample") or "")
    return int(raw) if raw.isdigit() and int(raw) > 8 else 8


def conversion_for(stream: dict, wide: bool = False) -> str:
    """The step to BT.709 an SDR stream needs, or nothing when its primaries already are: zscale where ffmpeg has it,
    else ffmpeg's own colorspace filter (built into every ffmpeg, no library needed), which converts the same
    primaries, matrix and transfer; with neither, swscale's rule, as for an untagged source. `wide` keeps the
    converted picture at sixteen (zscale) or twelve (colorspace) bits, 4:4:4, for a source decoded wide."""
    from .tools import has_filter

    primaries = str(stream.get("color_primaries") or "")
    transfer = str(stream.get("color_transfer") or "")
    if transfer in ("smpte2084", "arib-std-b67") or primaries in ("bt709", "") or primaries not in PRIMARIES:
        return ""
    matrix = str(stream.get("color_space") or "")
    source_matrix = matrix if matrix in MATRICES else ("bt2020nc" if primaries == "bt2020" else "smpte170m")
    source_transfer = transfer if transfer in TRANSFERS else "bt709"
    if has_filter("zscale"):
        layout = "yuv444p16le" if wide else "yuv420p"
        return f"zscale=pin={primaries}:min={source_matrix}:tin={source_transfer}:p=bt709:m=bt709:t=bt709:r=tv,format={layout},"
    if has_filter("colorspace"):
        _once("this ffmpeg has no zscale (it needs libzimg): wide-gamut clips are converted with its colorspace filter instead")
        space = "bt2020nc" if source_matrix == "bt2020c" else source_matrix
        source_range = "pc" if stream.get("color_range") == "pc" else "tv"
        layout = "yuv444p12" if wide else "yuv420p"
        return f"colorspace=iprimaries={primaries}:ispace={space}:itrc={source_transfer}:irange={source_range}:all=bt709:range=tv:format={layout},"
    _once("this ffmpeg has neither zscale nor colorspace: wide-gamut clips are shown with swscale's matrix only")
    return ""


def tonemap_for(stream: dict, wide: bool = False) -> str:
    """PQ and HLG to BT.709: linearised through zscale and tone-mapped with hable. An ffmpeg without zscale cannot do
    that; the clip is then converted by matrix alone (it shows, flatter than it should), and the terminal says so.
    `wide` keeps the result at sixteen bits, 4:4:4."""
    from .tools import has_filter

    layout = "yuv444p16le" if wide else "yuv420p"
    if has_filter("zscale") and has_filter("tonemap"):
        return f"zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format={layout},"
    _once(
        "this ffmpeg has no zscale (it needs libzimg): HDR clips are shown without tone mapping; an ffmpeg built with libzimg restores it"
    )
    return f"scale=in_color_matrix=bt2020:out_color_matrix=bt709,format={layout},"


def colour_of(stream: dict) -> dict:
    """What the record says about a source's colour: its space, and what the engine does with it."""
    transfer = str(stream.get("color_transfer") or "")
    primaries = str(stream.get("color_primaries") or "")
    if transfer == "smpte2084":
        return {"colour": "PQ (HDR10)", "colourHandling": "tone-mapped to Rec.709"}
    if transfer == "arib-std-b67":
        return {"colour": "HLG", "colourHandling": "tone-mapped to Rec.709"}
    if primaries == "bt2020":
        return {"colour": "BT.2020 SDR", "colourHandling": "converted to Rec.709"}
    if conversion_for(stream):
        return {"colour": primaries or str(stream.get("color_space") or "BT.601"), "colourHandling": "converted to Rec.709"}
    return {"colour": "Rec.709", "colourHandling": "as decoded"}


class VideoSource:
    def __init__(self, path, limit=None, deep: bool = False, precise: bool = False):
        self.path = str(path)
        # `precise`: an SDR timeline asks a source of more than eight bits (ten or twelve, 4:2:0, 4:2:2 or 4:4:4)
        # for sixteen-bit RGBA in its own signal, so a grade or a LUT works on its steps rather than on bytes.
        self.precise = bool(precise) and not deep
        # HDR working space, step 1: a deep source. With `deep`, a PQ or HLG stream is
        # delivered as sixteen-bit RGB in its own transfer, no tone-map, so the light
        # above white the camera recorded reaches the working space intact; an SDR
        # stream is unchanged. Frames come as uint16 RGB (not BGR) at 65535 full scale.
        self.deep = bool(deep)
        metadata = _ffprobe(path)
        stream = next((item for item in metadata.get("streams", []) if item.get("codec_type") == "video"), None)
        if stream is None:
            raise ValueError("This media has no video stream")
        if not stream.get("color_transfer"):
            # the decoder's own reading of the stream, when the probe named no colour (no ffprobe, a report that
            # did not say): the HDR decision must not hang on which programs a machine happens to have
            stream = {**_decoder_colours(self.path), **stream}
        self.colour_source = "probe" if stream.get("color_transfer") and "decoder_colours" not in stream else "decoder"
        self.width, self.height = int(stream["width"]), int(stream["height"])
        self.codec = str(stream.get("codec_name") or "")
        # X7: PQ and HLG decode washed out when read as if they were SDR. The
        # chain linearises through zscale, tone-maps with hable, and lands on
        # BT.709, the same recipe for preview and export because every decode
        # comes through this pipe.
        self.hdr = stream.get("color_transfer") in ("smpte2084", "arib-std-b67")
        self.bits = bit_depth(stream)
        # sixteen-bit RGBA comes out of the decoder: a deep HDR source in its own transfer, or a precise SDR one
        self.wide = (self.deep and self.hdr) or (self.precise and self.bits > 8)
        sdr_wide = self.wide and not self.deep
        self.tonemap = tonemap_for(stream, sdr_wide) if self.hdr else conversion_for(stream, sdr_wide)
        self.transfer = str(stream.get("color_transfer") or "")
        # what formcut's own conversion (yuv.py) needs of the stream, and whether the renderer takes planes from it
        self.matrix = str(stream.get("color_space") or "")
        self.full_range = stream.get("color_range") == "pc"
        self.want_planes = False
        self.own_conversion = False  # the renderer sets it (yuv.wanted)
        if self.deep and self.hdr:
            self.tonemap = ""  # the signal stays in its own transfer; nothing is rolled off
        # The quarter turns the picture is shown at, counter-clockwise, as np.rot90 counts them: the display matrix's
        # rotation is counter-clockwise degrees (-90 on a phone held upright), the legacy "rotate" tag clockwise.
        rotation = -float(stream.get("tags", {}).get("rotate", 0))
        for item in stream.get("side_data_list", []):
            if "rotation" in item:
                rotation = float(item["rotation"])
        self.turns = round(rotation / 90) % 4
        if self.turns % 2:
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
        self.key = (self.path, limit, self.deep, self.precise)
        self.last = None
        # R8: one frame read ahead on a thread while the caller renders.
        self.ahead = None
        self.ahead_thread = None
        self.ahead_lock = threading.Lock()

    def seek(self, frame):
        self.requested = max(0, int(frame))

    def _start(self):
        self.release()
        with self.ahead_lock:
            self.ahead = None
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
                f"{self.tonemap}fps={self.fps},scale={self.width}:{self.height}",
                "-threads",
                "1",
                "-pix_fmt",
                "rgba64le" if self.wide else "bgr24",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=self.errors,
        )

    def _active(self) -> bool:
        return self.process is not None

    def _pull(self):
        """One frame off the pipe into a fresh buffer, or None when the pipe ends."""
        deep = self.wide
        # a deep frame arrives as RGBA64 with its alpha already full, so nothing on this side adds a channel
        size = self.width * self.height * (8 if deep else 3)
        pieces = bytearray(size)
        view = memoryview(pieces)
        filled = 0
        while filled < size:
            count = self.process.stdout.readinto(view[filled:])
            if not count:
                view.release()
                return None
            filled += count
        view.release()
        if deep:
            return np.frombuffer(pieces, np.uint16).reshape(self.height, self.width, 4)
        return np.frombuffer(pieces, np.uint8).reshape(self.height, self.width, 3)

    def _prefetch(self):
        """R8: the frame after the one just served, read on a thread while the caller renders.

        Playback and export ask for consecutive frames; the pipe's next frame is
        always the one they will want, so it is pulled ahead into `ahead` and
        the next read() takes it without waiting on ffmpeg. A seek (a gap the
        sequential case does not cover) restarts the pipe and drops it."""
        with self.ahead_lock:
            if self.process is None or self.ahead is not None or self.ahead_thread is not None:
                return
            process = self.process
            position = self.position

            def pull():
                try:
                    frame = self._pull() if self.process is process else None
                except (OSError, ValueError):
                    frame = None  # the pipe was closed under the thread by a release
                with self.ahead_lock:
                    if self.process is process:
                        self.ahead = (position, frame)
                    self.ahead_thread = None

            self.ahead_thread = threading.Thread(target=pull, daemon=True)
            self.ahead_thread.start()

    def _take_ahead(self):
        """The prefetched frame, waiting for the thread if it is still pulling; None when there is none."""
        thread = self.ahead_thread
        if thread is not None:
            thread.join()
        with self.ahead_lock:
            ahead, self.ahead = self.ahead, None
            return ahead

    def read(self):
        if self.frame_count and self.requested >= self.frame_count:
            return False, None
        if self.last is not None and self.requested == self.last[0]:
            self.requested = self.position
            return True, self.last[1]
        gap = self.requested - self.position
        if not self._active() or gap < 0 or gap > max(1, round(self.fps * 2)):
            self._start()
        while True:
            ahead = self._take_ahead()
            frame = ahead[1] if ahead is not None and ahead[0] == self.position else self._pull()
            if frame is None:
                self.last_error = self._said()  # what the decoder said, kept before the release discards it
                self.release()
                return False, None
            self.position += 1
            if self.position > self.requested:
                break
        self.requested = self.position
        if self.key[1]:
            self.last = (self.position - 1, frame)
        self._prefetch()
        return True, frame

    def _said(self) -> str:
        """The decoder's own last words (ffmpeg's error output), for a read that failed."""
        errors = getattr(self, "errors", None)
        if errors is None:
            return ""
        try:
            errors.seek(0)
            text = errors.read().decode("utf-8", "replace").strip()
        except (OSError, ValueError):
            return ""
        return text[-400:]

    def release(self):
        thread = self.ahead_thread
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait()
            self.process.stdout.close()
            self.process = None
        if self.errors is not None:
            self.errors.close()
            self.errors = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)
        with self.ahead_lock:
            self.ahead = None
            self.ahead_thread = None


class NativeSource(VideoSource):
    """R23: the decoder in the engine. FFmpeg's libraries through PyAV, in-process: no pipe, no
    second process, the frame scaled by swscale into the buffer the passes upload. Each stream
    is decoded by whichever of the CPU and the chip is faster, measured once per codec and
    size on this machine (videotoolbox on macOS, d3d11va on Windows, vaapi or cuda on Linux),
    with the CPU as the fallback when the chip refuses the stream. An HDR source keeps the
    pipe until the HDR working space lands, because its tone-map lives in that filter chain.
    """

    def _start(self):
        self.release()
        with self.ahead_lock:
            self.ahead = None
        self.position = self.requested
        self.container = av.open(self.path, hwaccel=_hwaccel_for(self))
        self.stream = self.container.streams.video[0]
        self.stream.thread_type = "AUTO"
        base = self.stream.time_base
        # The stream's first moment, which frame 0 is counted from: an MPEG-TS or an offset file starts well after
        # zero (1.48 s is common), and counting from zero repeated its first frames and lost as many at the end.
        if self.stream.start_time is not None:
            self.origin = float(self.stream.start_time * base)
        elif self.container.start_time is not None:
            self.origin = self.container.start_time / 1_000_000
        else:
            self.origin = 0.0
        if self.position > 0:
            at = self.position / self.fps + self.origin
            self.container.seek(int(at / float(base)), stream=self.stream, backward=True, any_frame=False)
        self.decoded = self.container.decode(self.stream)
        self.native_index = -1  # the CFR index of the last frame decoded
        self.pending = None  # a decoded frame ahead of the CFR clock, held for duplication
        self.process = None
        self.errors = None
        # a seek lands on the keyframe before the target: decode forward to the target. A container that seeks by
        # byte position (MPEG-TS) can land past it instead; then the file is read again from its start.
        first = True
        while True:
            index, frame = self._next()
            if frame is None:
                break
            if first and index > self.position and self.position > 0:
                with contextlib.suppress(Exception):
                    self.container.close()
                self.container = av.open(self.path, hwaccel=_hwaccel_for(self))  # opened afresh, at its first frame
                self.stream = self.container.streams.video[0]
                self.stream.thread_type = "AUTO"
                self.decoded = self.container.decode(self.stream)
                first = False
                continue
            first = False
            if index >= self.position:
                self.pending = (index, frame)
                break

    def _active(self) -> bool:
        return getattr(self, "container", None) is not None

    def _prefetch(self):
        """The next frame decoded and scaled on a thread while the caller renders, as the pipe's R8 does: the M5
        profile showed the in-engine decoder decoding and scaling on the caller's thread, frame after frame."""
        with self.ahead_lock:
            container = getattr(self, "container", None)
            if container is None or self.ahead is not None or self.ahead_thread is not None:
                return
            position = self.position

            def pull():
                try:
                    frame = self._pull() if self.container is container else None
                except Exception:
                    frame = None
                with self.ahead_lock:
                    if self.container is container and frame is not None:
                        self.ahead = (position, frame)
                    self.ahead_thread = None

            self.ahead_thread = threading.Thread(target=pull, daemon=True)
            self.ahead_thread.start()

    def _next(self):
        """The next decoded frame with its constant-rate index, or (None, None) at the end."""
        try:
            frame = next(self.decoded)
        except (StopIteration, av.error.EOFError):
            return None, None
        except av.error.InvalidDataError:
            return self._next()
        seconds = float(frame.pts * self.stream.time_base) if frame.pts is not None else getattr(self, "origin", 0.0)
        index = round((seconds - getattr(self, "origin", 0.0)) * self.fps)
        return index, frame

    def _pull(self):
        """One frame at the CFR clock: a decoded frame ahead of the clock is repeated, one behind is dropped, as fps= does."""
        wanted = self.position
        while True:
            if self.pending is not None:
                index, frame = self.pending
                if index > wanted:
                    return self._as_bgr(frame)  # the clock has not reached it: repeat the picture
                self.pending = None
                if index == wanted:
                    self.last_frame = frame
                    return self._as_bgr(frame)
                self.last_frame = frame  # behind the clock: dropped, but kept in case the clock lands between
                continue
            index, frame = self._next()
            if frame is None:
                if getattr(self, "last_frame", None) is not None and self.frame_count and wanted < self.frame_count:
                    return self._as_bgr(self.last_frame)
                return None
            self.pending = (index, frame)

    def _as_bgr(self, frame):
        # A planar 4:2:0 frame at its own size is converted by formcut, not swscale: kept as its planes when the
        # renderer sends this clip to the device (which converts it in its first pass), converted here otherwise.
        turns = getattr(self, "turns", 0)
        if self.own_conversion and not turns and frame.width == self.width and frame.height == self.height:
            from .yuv import from_av

            planes = from_av(frame, self.wide, self.matrix, self.full_range)
            if planes is not None:
                return planes if self.want_planes else planes.rgba()
        # scaled at the stored size, then turned upright (the pipe's ffmpeg turns it by the same display matrix)
        width, height = (self.height, self.width) if turns % 2 else (self.width, self.height)
        if self.wide:
            # RGBA64 straight from swscale: the alpha is full already, so the renderer adds no channel (a 16 MB
            # copy a 1080p frame that the M5 profile showed)
            picture = frame.reformat(width=width, height=height, format="rgba64le", interpolation="BICUBIC").to_ndarray()
        else:
            picture = frame.reformat(width=width, height=height, format="bgr24", interpolation="BICUBIC").to_ndarray()
        return np.ascontiguousarray(np.rot90(picture, turns)) if turns else picture

    def release(self):
        # the read-ahead finishes before the container closes under it
        thread = self.ahead_thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)
        container = getattr(self, "container", None)
        if container is not None:
            with contextlib.suppress(Exception):
                container.close()
            self.container = None
            self.decoded = None
        with self.ahead_lock:
            self.ahead = None
            self.ahead_thread = None


_hw_choice: dict = {}
_hw_lock = threading.Lock()


def _device_type() -> str | None:
    if os.environ.get("FORMCUT_HWDEC") == "off":
        return None
    if sys.platform == "darwin":
        return "videotoolbox"
    if sys.platform.startswith("win"):
        return "d3d11va"
    return os.environ.get("FORMCUT_HWDEC_LINUX", "vaapi")


def _hwaccel_for(source: VideoSource):
    """The chip, when it decodes this stream and does so faster than the CPU, measured once per codec and size."""
    device = _device_type()
    if device is None:
        return None
    # the race runs the conversion the engine will run on this source: sixteen-bit RGBA for a deep HDR source,
    # eight-bit BGR otherwise; a chip that wins on BGR can lose once the frame has to come back at sixteen bits
    conversion = "rgba64le" if getattr(source, "wide", source.deep and source.hdr) else "bgr24"
    key = (source.codec, source.width, source.height, device, conversion)
    with _hw_lock:
        if key in _hw_choice:
            return _hw_choice[key]
        choice = None
        try:
            from av.codec.hwaccel import HWAccel

            hw = HWAccel(device_type=device, allow_software_fallback=False)
            fast = _decode_rate(source.path, hw, conversion=conversion)
            soft = _decode_rate(source.path, None, conversion=conversion)
            if fast and soft and fast > soft:
                choice = hw
        except Exception:
            choice = None
        _hw_choice[key] = choice
        return choice


def _decode_rate(path: str, hwaccel, frames: int = 24, conversion: str = "bgr24") -> float | None:
    began = time.perf_counter()
    try:
        with av.open(path, hwaccel=hwaccel) as container:
            stream = container.streams.video[0]
            stream.thread_type = "AUTO"
            count = 0
            for frame in container.decode(stream):
                frame.reformat(format=conversion)
                count += 1
                if count >= frames:
                    break
    except Exception:
        return None
    took = time.perf_counter() - began
    return count / took if took > 0 and count else None


_TRC = {
    1: "bt709",
    4: "gamma22",
    5: "gamma28",
    6: "smpte170m",
    7: "smpte240m",
    8: "linear",
    13: "iec61966-2-1",
    14: "bt2020-10",
    15: "bt2020-12",
    16: "smpte2084",
    18: "arib-std-b67",
}
_PRIMARIES = {1: "bt709", 5: "bt470bg", 6: "smpte170m", 7: "smpte240m", 9: "bt2020", 12: "smpte432"}
_MATRIX = {1: "bt709", 5: "bt470bg", 6: "smpte170m", 7: "smpte240m", 9: "bt2020nc", 10: "bt2020c"}
_RANGE = {1: "tv", 2: "pc"}


def _decoder_colours(path) -> dict:
    """A stream's colour as FFmpeg's decoder reads it from the stream itself (PyAV), in ffprobe's names."""
    if av is None:
        return {}
    try:
        with av.open(str(path)) as container:
            context = container.streams.video[0].codec_context
            found = {
                "color_transfer": _TRC.get(int(context.color_trc or 0)),
                "color_primaries": _PRIMARIES.get(int(context.color_primaries or 0)),
                "color_space": _MATRIX.get(int(context.colorspace or 0)),
                "color_range": _RANGE.get(int(context.color_range or 0)),
                "pix_fmt": getattr(context, "pix_fmt", None),
            }
    except Exception:
        return {}
    return {key: value for key, value in found.items() if value} | {"decoder_colours": True}


def _open(path, limit=None, deep: bool = False, precise: bool = False) -> VideoSource:
    """The decoder for this stream: in the engine when PyAV is here and the stream needs no tone-map (an SDR
    stream, or an HDR stream taken deep); the pipe otherwise, and always when FORMCUT_DECODE=pipe."""
    if av is not None and os.environ.get("FORMCUT_DECODE", "native") != "pipe":
        probe = VideoSource(path, limit, deep=deep, precise=precise)
        if not probe.tonemap:
            native = NativeSource.__new__(NativeSource)
            native.__dict__.update(probe.__dict__)
            return native
        return probe
    return VideoSource(path, limit, deep=deep, precise=precise)


_pool_lock = threading.Lock()
_idle: list[tuple[float, VideoSource]] = []


def forget_path(path) -> None:
    """Idle decoders of a file let go: its media was relinked to another file under the same name (linking.py)."""
    with _pool_lock:
        keep = []
        for stamp, source in _idle:
            if str(getattr(source, "path", "")) == str(path):
                with contextlib.suppress(Exception):
                    source.release()
            else:
                keep.append((stamp, source))
        _idle[:] = keep


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


def acquire(path, limit=None, at=None, deep: bool = False, precise: bool = False) -> VideoSource:
    key = (str(path), limit, deep, bool(precise) and not deep)
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
    return match[1] if match else _open(path, limit, deep=deep, precise=precise)


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
