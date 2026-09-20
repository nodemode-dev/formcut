#!/usr/bin/env python3
"""Export smoke checks and the RPC contract.

Two things that break quietly and are cheap to catch.

**Exports.** A render can succeed and still produce a file that is the wrong
size, the wrong length, or in a codec nothing will play. Checking the job said
"done" proves none of that. So each export here is read back with ffprobe and
compared against what was asked for.

**The RPC surface.** Anything driving formcut from outside depends on the shape
of these replies, not just on the call succeeding. A renamed field breaks every
caller and nothing here would fail. So each method is called and the keys of its
reply are checked against what is recorded below.

Both use generated content only, so they run anywhere with ffmpeg and need no
media on disk.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name:34s} {detail}")
    if not ok:
        FAILURES.append(f"{name}: {detail}")


def project(width: int, height: int, fps: int, duration: float) -> dict:
    """Generated content only: a title over a gradient, no media on disk."""
    return {
        "title": "Output check",
        "width": width,
        "height": height,
        "fps": fps,
        "duration": duration,
        "activeTimeline": 0,
        "background": {"type": "gradient", "from": "#101418", "to": "#2b3440"},
        "timelines": [
            {
                "id": "x",
                "name": "x",
                "tracks": [
                    {
                        "id": "t",
                        "name": "V",
                        "clips": [
                            {
                                "id": "a",
                                "kind": "text",
                                "label": "t",
                                "start": 0,
                                "duration": duration,
                                "textStyle": {
                                    "content": "FORMCUT",
                                    "size": 14,
                                    "color": "#ffcc55",
                                    "bold": True,
                                    "align": "center",
                                },
                                "keyframes": [
                                    {"t": 0, "props": {"scale": 60}, "interp": "ease"},
                                    {"t": duration, "props": {"scale": 110}, "interp": "linear"},
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def probe(path: Path) -> dict:
    """What actually came out, read from the file rather than assumed."""
    from app.tools import probe as read

    found = read(path)
    stream = next((s for s in found.get("streams", []) if s.get("codec_type") == "video"), {})
    rate = str(stream.get("avg_frame_rate") or "0/1")
    try:
        numerator, _, denominator = rate.partition("/")
        fps = float(numerator) / float(denominator or 1)
    except (TypeError, ValueError, ZeroDivisionError):
        fps = 0.0
    return {
        "codec": stream.get("codec_name"),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "fps": round(fps, 3),
        "duration": round(float(found.get("format", {}).get("duration") or 0), 2),
        "bytes": path.stat().st_size,
    }


def export_checks() -> None:
    from app import jobs
    from app.render_api import RenderInput, export

    print("\nexports, read back with ffprobe")
    cases = [
        ("h264 at 640x360", {"format": "mp4", "codec": "h264"}, 640, 360, 30, 2.0, "h264"),
        ("portrait 360x640", {"format": "mp4", "codec": "h264"}, 360, 640, 30, 2.0, "h264"),
        ("25 fps", {"format": "mp4", "codec": "h264"}, 640, 360, 25, 2.0, "h264"),
    ]
    for name, options, width, height, fps, duration, want_codec in cases:
        body = RenderInput(project=project(width, height, fps, duration), quality="medium", **options)
        started = export(body)
        job_id = started["job_id"] if isinstance(started, dict) else started.job_id
        state: dict = {}
        for _ in range(600):
            state = jobs.status(job_id)
            if state.get("status") in ("done", "error", "failed"):
                break
            time.sleep(1)
        if state.get("status") != "done":
            check(name, False, f"export did not finish: {str(state.get('error'))[:70]}")
            continue
        result = state.get("result") or {}
        path = Path(result.get("file") or result.get("path") or "")
        if not path.is_file():
            check(name, False, "job reported done but produced no file")
            continue
        facts = probe(path)
        wrong = []
        if facts["codec"] != want_codec:
            wrong.append(f"codec {facts['codec']}")
        if (facts["width"], facts["height"]) != (width, height):
            wrong.append(f"size {facts['width']}x{facts['height']}")
        if abs(facts["fps"] - fps) > 0.5:
            wrong.append(f"fps {facts['fps']}")
        if abs(facts["duration"] - duration) > 0.35:
            wrong.append(f"duration {facts['duration']}")
        if facts["bytes"] < 1024:
            wrong.append(f"only {facts['bytes']} bytes")
        check(
            name,
            not wrong,
            ", ".join(wrong) if wrong else f"{facts['codec']} {facts['width']}x{facts['height']} {facts['fps']}fps {facts['duration']}s",
        )


# The shape callers depend on. Values are the keys a reply must carry; a method
# may return more, never less.
RPC_CONTRACT: dict[str, tuple[dict, tuple[str, ...]]] = {
    "capabilities": ({}, ("edit_commands", "clip_properties", "methods")),
    "catalogue": ({}, ("video", "audio", "transitions")),
    "media.list": ({}, ()),
}


def rpc_checks() -> None:
    from app.automation import dispatch as handle

    print("\nRPC replies, checked for shape rather than for success")
    for method, (params, keys) in RPC_CONTRACT.items():
        try:
            reply = handle(method, params)
        except Exception as exc:  # noqa: BLE001 - a failing method is the finding
            check(method, False, f"raised {type(exc).__name__}: {str(exc)[:60]}")
            continue
        if keys:
            missing = [key for key in keys if key not in (reply or {})]
            check(method, not missing, "missing " + ", ".join(missing) if missing else f"carries {', '.join(keys)}")
        else:
            check(method, isinstance(reply, (list, dict)), f"returned {type(reply).__name__}")

    # A caller has to be able to see every verb and every property the app can
    # change. Masks and grades are set through clip.update rather than through a
    # command of their own, so they are checked among the properties, which is
    # where a caller would look for them.
    try:
        listed = handle("capabilities", {})
        commands = set(listed.get("edit_commands") or [])
        properties = set(listed.get("clip_properties") or [])
        missing_commands = sorted({"clip.add", "clip.update", "clips.split", "timeline.add"} - commands)
        missing_properties = sorted({"mask", "colour", "crop", "cutout", "key", "effects", "stabilise", "smoothSlow"} - properties)
        check(
            "capabilities lists edits",
            not missing_commands,
            "missing " + ", ".join(missing_commands) if missing_commands else f"{len(commands)} commands",
        )
        check(
            "capabilities lists properties",
            not missing_properties,
            "missing " + ", ".join(missing_properties) if missing_properties else f"{len(properties)} properties",
        )
    except Exception as exc:  # noqa: BLE001
        check("capabilities lists edits", False, str(exc)[:60])


def main() -> int:
    export_checks()
    rpc_checks()
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for line in FAILURES:
            print(f"  {line}")
        return 1
    print("exports and RPC replies are as expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
