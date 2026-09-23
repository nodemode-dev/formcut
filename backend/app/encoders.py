"""Encoder detection and codec selection (X1, X2).

`ffmpeg -encoders` lists what a build was compiled with, which is not the same
as what will run: a hardware encoder appears on a machine with the library but
no device. So a candidate is confirmed by encoding two generated frames with it
before it is offered, the same lesson the decode probe learned.
"""

from __future__ import annotations

import subprocess
import threading

# Per codec, in the order we would rather use: hardware first, software last.
CANDIDATES: dict[str, tuple[str, ...]] = {
    # The GPU makers' own encoders first, then VA-API (Intel and AMD on Linux)
    # and Media Foundation (Windows' encoders, a GPU's or Microsoft's own, so
    # every Windows 10 and 11 machine has one), then an installed libx264.
    "h264": ("h264_videotoolbox", "h264_nvenc", "h264_qsv", "h264_amf", "h264_vaapi", "h264_mf", "libx264"),
    "hevc": ("hevc_videotoolbox", "hevc_nvenc", "hevc_qsv", "hevc_amf", "hevc_vaapi", "hevc_mf", "libx265"),
    "av1": ("av1_nvenc", "av1_qsv", "libsvtav1", "libaom-av1"),
    "vp9": ("libvpx-vp9",),
    # ffmpeg's own MPEG-4 Part 2 encoder is in every build, the LGPL ones
    # included. An MP4 export uses it only when asked for by name: with no H.264
    # encoder, render_api uses Cisco's OpenH264 (openh264.py), then WebM.
    "mpeg4": ("mpeg4",),
}

CONTAINERS: dict[str, tuple[str, ...]] = {
    "mp4": ("h264", "hevc", "av1", "mpeg4"),
    "webm": ("vp9", "av1"),
}

# Quality tiers per encoder family, so one tier means the same thing to a user
# whichever codec they pick. Hardware encoders take a bitrate-ish quality scale
# rather than crf, hence the split.
TIERS: dict[str, dict[str, list[str]]] = {
    "libx264": {"high": ["-crf", "18"], "medium": ["-crf", "23"], "low": ["-crf", "28"]},
    "libx265": {"high": ["-crf", "20"], "medium": ["-crf", "26"], "low": ["-crf", "32"]},
    "libsvtav1": {"high": ["-crf", "26"], "medium": ["-crf", "34"], "low": ["-crf", "45"]},
    "libaom-av1": {"high": ["-crf", "26", "-b:v", "0"], "medium": ["-crf", "34", "-b:v", "0"], "low": ["-crf", "45", "-b:v", "0"]},
    "libvpx-vp9": {"high": ["-crf", "24", "-b:v", "0"], "medium": ["-crf", "33", "-b:v", "0"], "low": ["-crf", "40", "-b:v", "0"]},
    "_hardware": {"high": ["-q:v", "45"], "medium": ["-q:v", "60"], "low": ["-q:v", "75"]},
    "_nvenc": {"high": ["-cq", "21"], "medium": ["-cq", "28"], "low": ["-cq", "35"]},
    "_qsv": {"high": ["-global_quality", "21"], "medium": ["-global_quality", "28"], "low": ["-global_quality", "35"]},
    # AMF takes constant quantisers per frame type; -q:v means nothing to it.
    "_amf": {
        "high": ["-rc", "cqp", "-qp_i", "19", "-qp_p", "21"],
        "medium": ["-rc", "cqp", "-qp_i", "24", "-qp_p", "26"],
        "low": ["-rc", "cqp", "-qp_i", "29", "-qp_p", "31"],
    },
    # VA-API: a constant quantiser, the rate control every driver offers.
    "_vaapi": {
        "high": ["-rc_mode", "CQP", "-qp", "20"],
        "medium": ["-rc_mode", "CQP", "-qp", "25"],
        "low": ["-rc_mode", "CQP", "-qp", "30"],
    },
    # Media Foundation's quality mode, 0 to 100, which Microsoft's software
    # encoder supports as well as the GPUs' ones.
    "_mf": {
        "high": ["-rate_control", "quality", "-quality", "85"],
        "medium": ["-rate_control", "quality", "-quality", "70"],
        "low": ["-rate_control", "quality", "-quality", "55"],
    },
}

_lock = threading.Lock()
_detected: dict[str, list[str]] | None = None


def _listed() -> set[str]:
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, check=False, timeout=30).stdout
    except Exception:
        return set()
    names = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and len(parts[0]) == 6:
            names.add(parts[1])
    return names


VAAPI_DEVICE = "/dev/dri/renderD128"


def hardware_io(encoder: str) -> tuple[list[str], str | None]:
    """What an encoder needs around it: flags before the inputs, and a filter to end the chain.

    VA-API encoders take frames only in video memory, so they need the render
    device named before the inputs and an upload ending the filter chain, and
    no -pix_fmt after it. Every other encoder takes ordinary frames.
    """
    if encoder.endswith("_vaapi"):
        return ["-vaapi_device", VAAPI_DEVICE], "format=nv12,hwupload"
    return [], None


def _works(encoder: str) -> bool:
    """Encode two generated frames exactly as an export would; a listed encoder
    with no device, or refusing the quality flags, fails here and is skipped."""
    device, upload = hardware_io(encoder)
    try:
        probe = subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                *device,
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=320x240:rate=30:duration=0.1",
                "-frames:v",
                "2",
                *(["-vf", upload] if upload else []),
                "-c:v",
                encoder,
                *tier_flags(encoder, "high"),
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        return probe.returncode == 0
    except Exception:
        return False


def detect(refresh: bool = False) -> dict[str, list[str]]:
    """Working encoders per codec, in preference order. Probed once."""
    global _detected
    with _lock:
        if _detected is not None and not refresh:
            return _detected
        listed = _listed()
        found: dict[str, list[str]] = {}
        for codec, options in CANDIDATES.items():
            found[codec] = [name for name in options if name in listed and _works(name)]
        _detected = found
        return found


def choose(codec: str) -> str | None:
    """The encoder we would use for a codec, or None if none works here."""
    options = detect().get(codec) or []
    if options:
        return options[0]
    if codec == "h264":
        # Nothing built in can encode H.264, which is the expected state for an
        # LGPL ffmpeg on a machine with no hardware encoder. An add-on the
        # person installed themselves is asked last, never bundled.
        from .addons import h264_encoder

        found = h264_encoder()
        if found:
            return found[1]
    return None


def addon_binary_for(encoder: str):
    """The binary to run for an encoder, when it is not the bundled ffmpeg."""
    from .addons import h264_encoder

    found = h264_encoder()
    if found and found[1] == encoder:
        return found[0]
    return None


def tier_flags(encoder: str, quality: str) -> list[str]:
    """Quality flags for an encoder, falling back by family."""
    quality = quality if quality in ("high", "medium", "low") else "high"
    if encoder == "mpeg4":
        # A fixed quantiser gives each tier the same look at any frame size.
        return ["-q:v", {"high": "2", "medium": "4", "low": "8"}[quality]]
    if encoder in TIERS:
        return TIERS[encoder][quality]
    if encoder.endswith("_nvenc"):
        return TIERS["_nvenc"][quality]
    if encoder.endswith("_qsv"):
        return TIERS["_qsv"][quality]
    for family in ("_amf", "_vaapi", "_mf"):
        if encoder.endswith(family):
            return TIERS[family][quality]
    return TIERS["_hardware"][quality]


def status() -> dict:
    """What the export sheet may offer, per codec and per container."""
    found = detect()
    codecs = {
        codec: {"available": bool(options), "encoder": options[0] if options else None, "all": options} for codec, options in found.items()
    }
    # With no H.264 encoder here, an H.264 export goes through Cisco's OpenH264
    # (openh264.py), fetched the first time it is needed; offering H.264 keeps the
    # export sheet from falling to MPEG-4 Part 2 on the very machines it is for.
    if not codecs.get("h264", {}).get("available"):
        from . import openh264

        state = openh264.status()
        if state["supported"] and state["enabled"]:
            codecs["h264"] = {"available": True, "encoder": "libopenh264", "all": ["libopenh264"]}
    return {
        "codecs": codecs,
        "containers": {
            name: [codec for codec in members if codecs.get(codec, {}).get("available")] for name, members in CONTAINERS.items()
        },
    }


# X3: 10-bit is offered only where the encoder supports it; H.264 stays 8-bit
# because the 10-bit profile is poorly supported by the players people use.
TEN_BIT = {
    "libx265": "yuv420p10le",
    "libsvtav1": "yuv420p10le",
    "libaom-av1": "yuv420p10le",
    "libvpx-vp9": "yuv420p10le",
    "hevc_videotoolbox": "p010le",
    "hevc_nvenc": "p010le",
    "hevc_qsv": "p010le",
    "av1_nvenc": "p010le",
    "av1_qsv": "p010le",
}


def pixel_format(encoder: str, ten_bit: bool) -> str:
    """The pixel format to encode with; falls back to 8-bit where unsupported."""
    if ten_bit and encoder in TEN_BIT:
        return TEN_BIT[encoder]
    return "yuv420p"


def supports_ten_bit(codec: str) -> bool:
    chosen = choose(codec)
    return bool(chosen and chosen in TEN_BIT)


# X5: a size estimate for the export sheet. The shape is a power law in pixels
# per second, because bitrate does not scale linearly with resolution, and the
# constants below were fitted to real exports from this pipeline rather than
# guessed: h264/hevc/av1 at 320x180, 640x360 and 1280x720, plus the three
# quality tiers at 640x360. Measured bpp fell from 0.12 to 0.017 across that
# range, which is the exponent doing its job.
# Refitted after a 4K export came in 94 percent under. The first fit used a clip
# whose detail did not grow with resolution, which made bitrate look almost flat
# and produced an exponent of 0.30; measuring one clip at 360p, 720p, 1440p and
# 2160p gives about 0.85, which is also where the usual rule of thumb sits.
# Content still dominates: two clips at the same size can differ by more than
# this model's own error, so the estimate is a guide, not a promise.
BITRATE_K = 0.00095  # kbit/s at one unit of (pixels per second) ** EXPONENT
EXPONENT = 0.85
CODEC_FACTOR = {"h264": 1.0, "hevc": 0.683, "av1": 0.759, "vp9": 0.921, "mpeg4": 1.6}
# Quality factors are per codec, not shared: each encoder's tiers sit at
# different crf values, so AV1's high tier is 1.58x its medium where H.264's is
# 2.19x. Fitting one shared curve put an HEVC low-tier estimate 130 percent out.
QUALITY_FACTOR = {
    "h264": {"high": 2.19, "medium": 1.0, "low": 0.45},
    "hevc": {"high": 2.17, "medium": 1.0, "low": 0.46},
    "av1": {"high": 1.58, "medium": 1.0, "low": 0.59},
    "vp9": {"high": 2.07, "medium": 1.0, "low": 0.56},
}
AUDIO_KBPS = 128.0


def estimate_bitrate(codec: str, width: int, height: int, fps: float, quality: str) -> float:
    """Estimated video bitrate in kbit/s."""
    pixels = max(1.0, float(width) * float(height) * float(fps))
    base = BITRATE_K * (pixels**EXPONENT)
    tiers = QUALITY_FACTOR.get(codec, QUALITY_FACTOR["h264"])
    return base * CODEC_FACTOR.get(codec, 1.0) * tiers.get(quality, 1.0)


def estimate_size(codec: str, width: int, height: int, fps: float, quality: str, duration: float, has_audio: bool = True) -> dict:
    """Estimated output size in bytes, with the parts that made it up."""
    video = estimate_bitrate(codec, width, height, fps, quality)
    audio = AUDIO_KBPS if has_audio else 0.0
    total_bits = (video + audio) * 1000.0 * max(0.0, float(duration))
    return {
        "codec": codec,
        "quality": quality,
        "width": width,
        "height": height,
        "videoKbps": round(video, 1),
        "audioKbps": audio,
        "bytes": int(total_bits / 8),
        "seconds": duration,
    }
