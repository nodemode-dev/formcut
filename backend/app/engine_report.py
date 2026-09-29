"""What the engine runs on (v2.2.8): the native frame path, the GPU, and the ffmpeg in use.

The owner asked where the native engine had gone. Nothing said: formcut takes the native Rust frame path
(formcut_native, built into backend/venv by setup/build_native_gpu) when it is there and current, and the Python path,
slower, otherwise, without a word. Now the terminal says at start which one runs and, when it is not the native one,
why and what builds it; and it says which ffmpeg decodes and encodes, with what that ffmpeg has (zscale, VideoToolbox,
hardware decode). GET /api/engine gives the same.
"""

from __future__ import annotations

import contextlib
import subprocess
import sys

from fastapi import APIRouter

router = APIRouter(tags=["engine"])


def report() -> dict:
    from . import gpu, gpu_frame, tools

    native = gpu_frame.status()
    device = gpu.status()
    adapter = device.get("adapter") or {}
    binary = tools.ffmpeg()
    version = ""
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        version = subprocess.run(
            [binary, "-hide_banner", "-version"], capture_output=True, text=True, check=False, timeout=10
        ).stdout.split("\n", 1)[0]
    encoders = ""
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        encoders = subprocess.run([binary, "-hide_banner", "-encoders"], capture_output=True, text=True, check=False, timeout=10).stdout
    from .video_source import hwaccel_flags

    return {
        "native": {
            "running": bool(native.get("available")),
            "adapter": native.get("adapter"),
            "reason": native.get("reason"),
            "build": "setup/build_native_gpu",
        },
        "gpu": {
            "available": bool(device.get("available")),
            "name": adapter.get("device") or adapter.get("description") or adapter.get("name")
            if isinstance(adapter, dict)
            else str(adapter),
            "type": adapter.get("adapter_type") if isinstance(adapter, dict) else None,
            "compositor": device.get("compositor"),
            "stack": gpu.stack_active(),
        },
        "ffmpeg": {
            "path": binary,
            "version": version,
            "zscale": tools.has_filter("zscale"),
            "videotoolbox": "h264_videotoolbox" in encoders,
            "hardwareDecode": " ".join(hwaccel_flags()) or None,
        },
    }


def say() -> None:
    """The report, in the terminal, as a person reads it."""
    try:
        state = report()
    except Exception as exc:  # noqa: BLE001 - a report that fails must not stop the engine
        print(f"formcut: could not report the engine ({exc})", file=sys.__stderr__)
        return
    native, device, ffmpeg = state["native"], state["gpu"], state["ffmpeg"]
    lines = []
    if native["running"]:
        lines.append(f"native engine: running (the Rust frame path, on {native['adapter']})")
    else:
        lines.append(f"native engine: NOT running, the Python path is used (slower): {native['reason']}")
        if any(word in str(native["reason"]) for word in ("No module named", "ImportError", "older build")):
            lines.append("  to build it: setup/build_native_gpu (needs Rust: https://rustup.rs), then start formcut again")
    lines.append(
        f"GPU: {device['name']} ({device['type']}), compositing on the {'GPU' if device['stack'] else 'CPU'}"
        if device["available"]
        else "GPU: none found, compositing on the CPU"
    )
    lines.append(
        f"ffmpeg: {ffmpeg['path']} ({ffmpeg['version'] or 'version unknown'}); zscale {'yes' if ffmpeg['zscale'] else 'no'}, "
        f"VideoToolbox {'yes' if ffmpeg['videotoolbox'] else 'no'}, hardware decode {ffmpeg['hardwareDecode'] or 'none'}"
    )
    for line in lines:
        print(f"formcut: {line}", file=sys.__stderr__)


@router.get("/api/engine")
def engine() -> dict:
    return report()
