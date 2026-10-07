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

Format = Literal["srt", "vtt", "scc"]
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
    if body.lstrip().startswith("Scenarist_SCC"):
        return parse_scc(body)
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
    """SRT, WebVTT or SCC text for the cues, in time order."""
    ordered = sorted(cues, key=lambda cue: cue.start)
    if fmt == "scc":
        return write_scc(ordered)
    blocks = []
    for index, cue in enumerate(ordered, start=1):
        head = f"{index}\n" if fmt == "srt" else ""
        blocks.append(f"{head}{_stamp(cue.start, fmt)} --> {_stamp(cue.end, fmt)}\n{cue.text.strip()}")
    text = "\n\n".join(blocks)
    return ("WEBVTT\n\n" + text if fmt == "vtt" else text) + "\n"


# ---------------------------------------------------------------------------------------------- SCC (CEA-608)
# Scenarist SCC: CEA-608 byte pairs as hex, pop-on captions on channel 1 at 29.97 drop-frame. Every code is computed
# from the standard with odd parity (RCL 9420, ENM 94ae, EOC 942f, EDM 942c; rows 14 and 15 at indent 0 are 94d0 and
# 9470), not written from memory. After FilmCraft's captions crate, which lists SCC among its formats.

SCC_FPS = 30000 / 1001
SCC_ROW = 32  # characters a 608 row holds
SCC_SPECIAL = {"á": 0x2A, "é": 0x5C, "í": 0x5E, "ó": 0x5F, "ú": 0x60, "ç": 0x7B, "÷": 0x7C, "Ñ": 0x7D, "ñ": 0x7E, "█": 0x7F}
SCC_DECODE = {code: char for char, code in SCC_SPECIAL.items()}
# ASCII characters whose codes the 608 basic set gives to the letters above, written as their nearest kin
SCC_STAND_IN = {"*": "-", "\\": "/", "^": "-", "_": "-", "`": "'", "{": "(", "|": "/", "}": ")", "~": "-"}


def _odd(byte: int) -> int:
    return byte | 0x80 if byte.bit_count() % 2 == 0 else byte


def _word(a: int, b: int) -> str:
    return f"{_odd(a):02x}{_odd(b):02x}"


RCL, ENM, EOC, EDM = _word(0x14, 0x20), _word(0x14, 0x2E), _word(0x14, 0x2F), _word(0x14, 0x2C)
ROW14, ROW15 = _word(0x14, 0x50), _word(0x14, 0x70)


def _df_timecode(frames: int) -> str:
    """29.97 drop-frame timecode: frame numbers 0 and 1 are skipped each minute but every tenth."""
    tens, rest = divmod(max(0, frames), 17982)
    frames += 18 * tens + (2 * ((rest - 2) // 1798) if rest > 1 else 0)
    return f"{frames // 108000:02d}:{frames // 1800 % 60:02d}:{frames // 30 % 60:02d};{frames % 30:02d}"


def _df_frames(hours: int, minutes: int, seconds: int, frames: int, drop: bool) -> int:
    total = ((hours * 60 + minutes) * 60 + seconds) * 30 + frames
    if drop:
        whole = hours * 60 + minutes
        total -= 2 * (whole - whole // 10)
    return total


def _scc_text(line: str) -> list[str]:
    import unicodedata

    codes = []
    for original in line:
        char = SCC_STAND_IN.get(original, original)
        if char in SCC_SPECIAL:
            codes.append(SCC_SPECIAL[char])
            continue
        plain = unicodedata.normalize("NFKD", char).encode("ascii", "ignore").decode() or ""
        codes.extend(ord(c) for c in plain[:1] if 0x20 <= ord(c) < 0x7F and c not in SCC_STAND_IN)
    if len(codes) % 2:
        codes.append(0x00)
    return [_word(codes[i], codes[i + 1]) for i in range(0, len(codes), 2)]


def _scc_rows(text: str) -> list[str]:
    rows = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            rest = word
            while len(rest) > SCC_ROW:
                if line:
                    rows.append(line)
                    line = ""
                rows.append(rest[:SCC_ROW])
                rest = rest[SCC_ROW:]
            if line and len(line) + 1 + len(rest) > SCC_ROW:
                rows.append(line)
                line = rest
            else:
                line = f"{line} {rest}".strip()
        if line:
            rows.append(line)
    return rows


def write_scc(cues: list[Cue]) -> str:
    """Pop-on captions: each is loaded into the hidden memory ahead of its start (one word a frame) so its EOC lands on
    the start; it is erased at its end unless the next caption replaces it there. Over two rows splits the cue."""
    captions: list[tuple[int, int, list[str]]] = []
    for cue in cues:
        rows = _scc_rows(cue.text) or [""]
        chunks = [rows[i : i + 2] for i in range(0, len(rows), 2)]
        span = (cue.end - cue.start) / len(chunks)
        for n, chunk in enumerate(chunks):
            words = [ENM, ENM, RCL, RCL]
            for r, line in enumerate(chunk):
                pac = ROW14 if len(chunk) == 2 and r == 0 else ROW15
                words += [pac, pac, *_scc_text(line)]
            words += [EOC, EOC]
            start = cue.start + n * span
            captions.append((round(start * SCC_FPS), round((start + span) * SCC_FPS), words))
    lines = ["Scenarist_SCC V1.0", ""]
    busy = 0
    for i, (show, end, words) in enumerate(captions):
        # the caption appears at its first EOC, two words before the load ends
        load = max(show - (len(words) - 2), busy)
        lines += [f"{_df_timecode(load)}\t{' '.join(words)}", ""]
        busy = load + len(words)
        following = captions[i + 1][0] if i + 1 < len(captions) else None
        if following is None or following > end + 1:
            at = max(end, busy)
            lines += [f"{_df_timecode(at)}\t{EDM} {EDM}", ""]
            busy = at + 2
    return "\n".join(lines)


def parse_scc(text: str) -> list[Cue]:
    """Pop-on captions on channel 1: text loads into a hidden memory, EOC shows it (ending the one shown), EDM clears
    it. Doubled control codes count once; channels 2 to 4, roll-up and paint-on are not read."""
    cues: list[Cue] = []
    hidden: list[str] = []
    shown: tuple[str, float] | None = None
    last = None
    at = 0.0
    for raw in text.splitlines():
        hit = re.match(r"^(\d\d):(\d\d):(\d\d)([:;.,])(\d\d)\s+(.+)$", raw.strip())
        if not hit:
            continue
        frame = _df_frames(*(int(hit.group(i)) for i in (1, 2, 3, 5)), drop=hit.group(4) in ";,")
        for k, word in enumerate(hit.group(6).split()):
            at = (frame + k) / SCC_FPS
            try:
                a, b = int(word[:2], 16) & 0x7F, int(word[2:4], 16) & 0x7F
            except ValueError:
                continue
            if 0x10 <= a <= 0x1F:
                if (a, b) == last:
                    last = None
                    continue
                last = (a, b)
                if a in (0x14, 0x15) and 0x20 <= b <= 0x2F:
                    if b == 0x2E:
                        hidden = []
                    elif b == 0x2F:
                        if shown:
                            cues.append(Cue(start=round(shown[1], 3), end=round(at, 3), text=shown[0]))
                        content = "\n".join(line.strip() for line in hidden if line.strip())
                        shown = (content, at) if content else None
                        hidden = []
                    elif b == 0x2C and shown:
                        cues.append(Cue(start=round(shown[1], 3), end=round(at, 3), text=shown[0]))
                        shown = None
                elif a <= 0x17 and b >= 0x40:
                    hidden.append("")
                elif a == 0x11 and 0x30 <= b <= 0x3F:
                    hidden[-1:] = [(hidden[-1] if hidden else "") + {0x37: "♪"}.get(b, "")]
                continue
            last = None
            for code in (a, b):
                if code >= 0x20:
                    if not hidden:
                        hidden.append("")
                    hidden[-1] += SCC_DECODE.get(code, chr(code))
    if shown:
        cues.append(Cue(start=round(shown[1], 3), end=round(at + 2, 3), text=shown[0]))
    return [cue for cue in cues if cue.end > cue.start and cue.text]


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
        raise HTTPException(422, "no cues found: expected SRT, WebVTT or SCC")
    return {"cues": [cue.model_dump() for cue in cues]}


@router.post("/write")
def write_file(body: WriteBody) -> Response:
    if not body.cues:
        raise HTTPException(422, "no cues to write")
    media_type = {"vtt": "text/vtt", "scc": "text/plain"}.get(body.format, "application/x-subrip")
    return Response(
        write(body.cues, body.format),
        media_type=f"{media_type}; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="captions.{body.format}"'},
    )
