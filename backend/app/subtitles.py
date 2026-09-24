"""Subtitle files: SRT and WebVTT, written from caption clips and read back.

A transcript leaves formcut for a platform's own caption track, and a corrected
one comes back onto the timeline, as cues of text, start and end. On read, VTT
NOTE blocks, cue identifiers, cue settings and inline tags are dropped; the cue
text is kept with its line breaks. Times are seconds; the writer rounds to
milliseconds.
"""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/api/subtitles", tags=["subtitles"])

Format = Literal["srt", "vtt"]
TIME = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})")
ARROW = re.compile(r"-->")
TAG = re.compile(r"</?[^>]+>")


class Cue(BaseModel):
    start: float
    end: float
    text: str


def _seconds(stamp: str) -> float:
    match = TIME.fullmatch(stamp.strip())
    if not match:
        raise ValueError(f"not a time: {stamp!r}")
    hours, minutes, seconds, fraction = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds) + int(fraction.ljust(3, "0")) / 1000


def parse(text: str) -> list[Cue]:
    """Cues from SRT or WebVTT text, in the file's order."""
    body = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    cues: list[Cue] = []
    for block in re.split(r"\n{2,}", body.strip()):
        lines = [line for line in block.split("\n") if line.strip()]
        if not lines or lines[0].startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
            continue
        timing = next((i for i, line in enumerate(lines) if ARROW.search(line)), None)
        if timing is None:
            continue
        start_stamp, end_stamp = ARROW.split(lines[timing], maxsplit=1)
        end_stamp = end_stamp.strip().split(" ", 1)[0]
        try:
            start, end = _seconds(start_stamp), _seconds(end_stamp)
        except ValueError:
            continue
        content = "\n".join(TAG.sub("", line) for line in lines[timing + 1 :]).strip()
        if content and end > start:
            cues.append(Cue(start=round(start, 3), end=round(end, 3), text=content))
    return cues


def _stamp(seconds: float, fmt: Format) -> str:
    total = max(0, round(seconds * 1000))
    hours, rest = divmod(total, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    separator = "," if fmt == "srt" else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def write(cues: list[Cue], fmt: Format) -> str:
    """SRT or WebVTT text for the cues, in time order."""
    ordered = sorted(cues, key=lambda cue: cue.start)
    blocks = []
    for index, cue in enumerate(ordered, start=1):
        head = f"{index}\n" if fmt == "srt" else ""
        blocks.append(f"{head}{_stamp(cue.start, fmt)} --> {_stamp(cue.end, fmt)}\n{cue.text.strip()}")
    text = "\n\n".join(blocks)
    return ("WEBVTT\n\n" + text if fmt == "vtt" else text) + "\n"


class WriteBody(BaseModel):
    cues: list[Cue]
    format: Format = "srt"


@router.post("/parse")
async def parse_file(file: UploadFile) -> dict:
    raw = await file.read()
    if len(raw) > 4_000_000:
        raise HTTPException(413, "a subtitle file this large is not a subtitle file")
    cues = parse(raw.decode("utf-8", errors="replace"))
    if not cues:
        raise HTTPException(422, "no cues found: expected SRT or WebVTT")
    return {"cues": [cue.model_dump() for cue in cues]}


@router.post("/write")
def write_file(body: WriteBody) -> Response:
    if not body.cues:
        raise HTTPException(422, "no cues to write")
    media_type = "text/vtt" if body.format == "vtt" else "application/x-subrip"
    return Response(
        write(body.cues, body.format),
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="captions.{body.format}"'},
    )
