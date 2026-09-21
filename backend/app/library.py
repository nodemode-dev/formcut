"""Stickers, music and sound effects that formcut makes itself.

Every item here is drawn or synthesised by the code in this module, so the app
ships no media files for it, owes nobody a licence for it, and makes the same
item on every machine. An item is rendered into the data directory the first
time it is asked for and kept; a version stamp re-renders a kind when the code
that makes it changes. All of it is free to use in any video, commercial or
not, with no attribution.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
import threading
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, ImageDraw, ImageFont

from . import media
from .paths import DATA_DIR

router = APIRouter(prefix="/api/library", tags=["library"])

VERSION = "1"
LICENCE = "Made by formcut: free to use in any video, no credit needed"
LIBRARY_DIR = DATA_DIR / "library"
SIZE = 512
S = SIZE * 4  # stickers are drawn at four times their size and reduced, which smooths every edge
C = S / 2
SOUND_RATE = 48000
MUSIC_RATE = 44100
TAIL = 2.0  # seconds a track rings on after its last bar
_lock = threading.Lock()

INK = (27, 27, 31, 255)
PAPER = (255, 255, 255, 255)
SUN = (255, 200, 61, 255)
CORAL = (255, 90, 95, 255)
TEAL = (31, 200, 169, 255)
BLUE = (61, 123, 255, 255)
VIOLET = (138, 92, 255, 255)
ORANGE = (255, 138, 36, 255)
CLEAR = (0, 0, 0, 0)


@dataclass(frozen=True)
class Item:
    id: str
    name: str
    category: str
    make: Callable
    seconds: float = 0.0
    bpm: int = 0


# Stickers ------------------------------------------------------------------


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    art = Image.new("RGBA", (S, S), CLEAR)
    return art, ImageDraw.Draw(art)


def _star(cx: float, cy: float, outer: float, inner: float, points: int = 5, turn: float = -90) -> list[tuple[float, float]]:
    corners = []
    for index in range(points * 2):
        radius = outer if index % 2 == 0 else inner
        angle = math.radians(turn + index * 180 / points)
        corners.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return corners


def _heart(cx: float, cy: float, size: float) -> list[tuple[float, float]]:
    outline = []
    for index in range(240):
        t = 2 * math.pi * index / 240
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        outline.append((cx + x * size / 17, cy - y * size / 17))
    return outline


def _disc(draw: ImageDraw.ImageDraw, x: float, y: float, radius: float, fill) -> None:
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=fill)


def _stroke(draw: ImageDraw.ImageDraw, points: list[tuple[float, float]], width: int, fill) -> None:
    """A thick line with round ends and joints."""
    draw.line(points, fill=fill, width=width, joint="curve")
    for x, y in (points[0], points[-1]):
        _disc(draw, x, y, width / 2, fill)


def _words(draw: ImageDraw.ImageDraw, x: float, y: float, text: str, size: int, fill) -> None:
    """Heavy lettering: glyphs drawn as a mask and thickened by distance, which stays solid where a stroked outline cracks."""
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).text((x, y), text, font=ImageFont.load_default(size=size), fill=255, anchor="mm")
    reach = cv2.distanceTransform((np.asarray(mask) < 128).astype(np.uint8), cv2.DIST_L2, 5)
    draw.bitmap((0, 0), Image.fromarray((np.clip(size / 28 + 1 - reach, 0, 1) * 255).astype(np.uint8)), fill=fill)


def _finish(art: Image.Image) -> Image.Image:
    """Give the art a white sticker edge and a soft shadow, then reduce it to size."""
    outside = (np.asarray(art)[:, :, 3] < 128).astype(np.uint8)
    distance = cv2.distanceTransform(outside, cv2.DIST_L2, 5)
    edge = (np.clip(49.0 - distance, 0.0, 1.0) * 255).astype(np.uint8)
    small = cv2.GaussianBlur(cv2.resize(edge, (SIZE, SIZE), interpolation=cv2.INTER_AREA), (0, 0), 5)
    blur = cv2.resize(small, (S, S), interpolation=cv2.INTER_LINEAR)
    shade = np.zeros((S, S, 4), np.uint8)
    shade[28:, 12:, 3] = (blur[:-28, :-12].astype(np.float32) * 0.35).astype(np.uint8)
    white = np.zeros((S, S, 4), np.uint8)
    white[:, :, :3] = 255
    white[:, :, 3] = edge
    out = Image.alpha_composite(Image.fromarray(shade, "RGBA"), Image.fromarray(white, "RGBA"))
    return Image.alpha_composite(out, art).resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def _face() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    art, draw = _canvas()
    _disc(draw, C, C, 820, SUN)
    return art, draw


def _eyes(draw: ImageDraw.ImageDraw, width: float = 80, height: float = 130) -> None:
    for x in (C - 330, C + 330):
        draw.ellipse((x - width, C - 260 - height, x + width, C - 260 + height), fill=INK)


def star():
    art, draw = _canvas()
    draw.polygon(_star(C, C + 60, 860, 360), fill=SUN)
    return art


def heart():
    art, draw = _canvas()
    draw.polygon(_heart(C, C - 110, 700), fill=CORAL)
    return art


def sparkle():
    art, draw = _canvas()
    draw.polygon(_star(C - 60, C + 60, 800, 180, points=4), fill=TEAL)
    draw.polygon(_star(C + 520, C - 520, 250, 60, points=4), fill=TEAL)
    return art


def lightning():
    art, draw = _canvas()
    draw.polygon(
        [
            (C + 150, C - 840),
            (C - 470, C + 90),
            (C - 60, C + 90),
            (C - 220, C + 850),
            (C + 470, C - 170),
            (C + 50, C - 170),
            (C + 300, C - 840),
        ],
        fill=SUN,
    )
    return art


def flame():
    art, draw = _canvas()
    draw.ellipse((C - 560, C - 40, C + 560, C + 820), fill=ORANGE)
    draw.polygon([(C - 545, C + 300), (C - 140, C - 860), (C + 60, C - 380), (C + 300, C - 640), (C + 545, C + 300)], fill=ORANGE)
    draw.ellipse((C - 300, C + 260, C + 300, C + 780), fill=SUN)
    draw.polygon([(C - 292, C + 500), (C - 40, C - 240), (C + 110, C + 60), (C + 292, C + 500)], fill=SUN)
    return art


def crown():
    art, draw = _canvas()
    draw.polygon(
        [
            (C - 760, C + 460),
            (C - 820, C - 360),
            (C - 380, C + 40),
            (C, C - 560),
            (C + 380, C + 40),
            (C + 820, C - 360),
            (C + 760, C + 460),
        ],
        fill=SUN,
    )
    draw.rounded_rectangle((C - 780, C + 420, C + 780, C + 660), radius=60, fill=SUN)
    for x, y in ((C - 820, C - 360), (C, C - 560), (C + 820, C - 360)):
        _disc(draw, x, y, 100, SUN)
    for x, colour in ((C - 420, CORAL), (C, TEAL), (C + 420, CORAL)):
        _disc(draw, x, C + 540, 70, colour)
    return art


def arrow_right():
    art, draw = _canvas()
    draw.polygon(
        [
            (C - 820, C - 190),
            (C + 120, C - 190),
            (C + 120, C - 520),
            (C + 840, C),
            (C + 120, C + 520),
            (C + 120, C + 190),
            (C - 820, C + 190),
        ],
        fill=CORAL,
    )
    return art


def arrow_down():
    art, draw = _canvas()
    draw.polygon(
        [
            (C - 190, C - 840),
            (C + 190, C - 840),
            (C + 190, C - 100),
            (C + 520, C - 100),
            (C, C + 840),
            (C - 520, C - 100),
            (C - 190, C - 100),
        ],
        fill=VIOLET,
    )
    return art


def arrow_curved():
    art, draw = _canvas()
    cx, cy, radius = C, C + 260, 700
    draw.arc((cx - radius, cy - radius, cx + radius, cy + radius), start=200, end=322, fill=BLUE, width=230)
    angle = math.radians(322)
    x, y = cx + radius * math.cos(angle), cy + radius * math.sin(angle)
    ahead, side = (-math.sin(angle), math.cos(angle)), (math.cos(angle), math.sin(angle))
    tip = (x + 330 * ahead[0], y + 330 * ahead[1])
    draw.polygon([tip, (x + 290 * side[0], y + 290 * side[1]), (x - 290 * side[0], y - 290 * side[1])], fill=BLUE)
    start = math.radians(200)
    _disc(draw, cx + radius * math.cos(start), cy + radius * math.sin(start), 115, BLUE)
    return art


def chevrons():
    art, draw = _canvas()
    for left in (C - 820, C - 180):
        draw.polygon(
            [(left, C - 620), (left + 300, C - 620), (left + 720, C), (left + 300, C + 620), (left, C + 620), (left + 420, C)], fill=TEAL
        )
    return art


def speech():
    art, draw = _canvas()
    draw.rounded_rectangle((C - 820, C - 620, C + 820, C + 420), radius=300, fill=INK)
    draw.polygon([(C - 420, C + 300), (C - 560, C + 800), (C - 60, C + 380)], fill=INK)
    draw.rounded_rectangle((C - 776, C - 576, C + 776, C + 376), radius=260, fill=PAPER)
    draw.polygon([(C - 392, C + 330), (C - 500, C + 700), (C - 110, C + 360)], fill=PAPER)
    for x in (C - 380, C, C + 380):
        _disc(draw, x, C - 100, 90, INK)
    return art


def thought():
    art, draw = _canvas()
    for x, y, radius in ((C, C - 140, 0), (C - 560, C + 470, 130), (C - 760, C + 700, 80)):
        if radius:
            _disc(draw, x, y, radius, INK)
            _disc(draw, x, y, radius - 44, PAPER)
    draw.ellipse((C - 800, C - 640, C + 800, C + 360), fill=INK)
    draw.ellipse((C - 756, C - 596, C + 756, C + 316), fill=PAPER)
    return art


def circle_mark():
    art, draw = _canvas()
    draw.ellipse((C - 820, C - 560, C + 820, C + 560), outline=CORAL, width=110)
    draw.ellipse((C - 780, C - 610, C + 860, C + 500), outline=CORAL, width=70)
    return art


def underline():
    art, draw = _canvas()
    points = [(C - 800 + 1600 * step / 40, C + 60 - 170 * math.sin(math.pi * step / 40) + 60 * step / 40) for step in range(41)]
    _stroke(draw, points, 200, SUN)
    return art


def check():
    art, draw = _canvas()
    _disc(draw, C, C, 820, TEAL)
    _stroke(draw, [(C - 420, C + 20), (C - 110, C + 330), (C + 460, C - 300)], 200, PAPER)
    return art


def cross():
    art, draw = _canvas()
    _disc(draw, C, C, 820, CORAL)
    _stroke(draw, [(C - 360, C - 360), (C + 360, C + 360)], 200, PAPER)
    _stroke(draw, [(C + 360, C - 360), (C - 360, C + 360)], 200, PAPER)
    return art


def exclamation():
    art, draw = _canvas()
    draw.polygon([(C, C - 820), (C + 880, C + 700), (C - 880, C + 700)], fill=SUN)
    draw.rounded_rectangle((C - 90, C - 360, C + 90, C + 300), radius=90, fill=INK)
    _disc(draw, C, C + 480, 100, INK)
    return art


def question():
    art, draw = _canvas()
    _disc(draw, C, C, 820, VIOLET)
    _words(draw, C, C + 40, "?", 1150, PAPER)
    return art


def new():
    art, draw = _canvas()
    draw.polygon(_star(C, C, 860, 700, points=16), fill=CORAL)
    _words(draw, C, C + 20, "NEW", 500, PAPER)
    return art


def sale():
    art, draw = _canvas()
    draw.polygon([(C - 560, C - 520), (C + 820, C - 520), (C + 820, C + 520), (C - 560, C + 520), (C - 860, C)], fill=SUN)
    _disc(draw, C - 560, C, 90, CLEAR)
    _words(draw, C + 150, C + 10, "SALE", 400, INK)
    return art


def live():
    art, draw = _canvas()
    draw.rounded_rectangle((C - 820, C - 340, C + 820, C + 340), radius=340, fill=CORAL)
    _disc(draw, C - 500, C, 110, PAPER)
    _words(draw, C + 130, C + 10, "LIVE", 440, PAPER)
    return art


def wow():
    art, draw = _canvas()
    draw.polygon(_star(C, C, 880, 600, points=12), fill=VIOLET)
    _words(draw, C, C + 20, "WOW!", 420, PAPER)
    return art


def follow():
    art, draw = _canvas()
    draw.rounded_rectangle((C - 840, C - 300, C + 840, C + 300), radius=300, fill=BLUE)
    _words(draw, C, C + 10, "+ FOLLOW", 290, PAPER)
    return art


def smile():
    art, draw = _face()
    _eyes(draw)
    draw.arc((C - 480, C - 360, C + 480, C + 440), start=20, end=160, fill=INK, width=90)
    return art


def wink():
    art, draw = _face()
    draw.ellipse((C - 410, C - 390, C - 250, C - 130), fill=INK)
    draw.arc((C + 190, C - 330, C + 470, C - 110), start=200, end=340, fill=INK, width=70)
    draw.arc((C - 480, C - 360, C + 480, C + 440), start=20, end=160, fill=INK, width=90)
    return art


def laugh():
    art, draw = _face()
    for x in (C - 330, C + 330):
        draw.arc((x - 150, C - 360, x + 150, C - 120), start=200, end=340, fill=INK, width=70)
    draw.pieslice((C - 500, C - 200, C + 500, C + 560), start=0, end=180, fill=INK)
    draw.ellipse((C - 240, C + 280, C + 240, C + 520), fill=CORAL)
    return art


def surprised():
    art, draw = _face()
    _eyes(draw, 95, 150)
    draw.ellipse((C - 150, C + 140, C + 150, C + 520), fill=INK)
    return art


def heart_eyes():
    art, draw = _face()
    for x in (C - 330, C + 330):
        draw.polygon(_heart(x, C - 280, 210), fill=CORAL)
    draw.arc((C - 480, C - 360, C + 480, C + 440), start=20, end=160, fill=INK, width=90)
    return art


def cool():
    art, draw = _face()
    draw.rounded_rectangle((C - 640, C - 400, C - 80, C - 80), radius=110, fill=INK)
    draw.rounded_rectangle((C + 80, C - 400, C + 640, C - 80), radius=110, fill=INK)
    _stroke(draw, [(C - 120, C - 320), (C + 120, C - 320)], 60, INK)
    draw.arc((C - 300, C - 100, C + 420, C + 420), start=20, end=140, fill=INK, width=90)
    return art


def music_note():
    art, draw = _canvas()
    draw.ellipse((C - 640, C + 260, C - 100, C + 680), fill=VIOLET)
    draw.rectangle((C - 200, C - 740, C - 100, C + 470), fill=VIOLET)
    draw.polygon([(C - 200, C - 740), (C + 480, C - 520), (C + 480, C - 220), (C - 100, C - 420)], fill=VIOLET)
    return art


def bell():
    art, draw = _canvas()
    draw.ellipse((C - 430, C - 700, C + 430, C + 100), fill=SUN)
    draw.polygon([(C - 430, C - 300), (C + 430, C - 300), (C + 640, C + 440), (C - 640, C + 440)], fill=SUN)
    draw.rounded_rectangle((C - 720, C + 400, C + 720, C + 550), radius=70, fill=SUN)
    _disc(draw, C, C + 650, 140, ORANGE)
    _disc(draw, C, C - 710, 100, SUN)
    return art


def pin():
    art, draw = _canvas()
    _disc(draw, C, C - 260, 560, CORAL)
    draw.polygon([(C - 500, C - 40), (C + 500, C - 40), (C, C + 850)], fill=CORAL)
    _disc(draw, C, C - 260, 210, PAPER)
    return art


STICKERS = [
    Item("star", "Star", "Shapes", star),
    Item("heart", "Heart", "Shapes", heart),
    Item("sparkle", "Sparkle", "Shapes", sparkle),
    Item("lightning", "Lightning", "Shapes", lightning),
    Item("flame", "Flame", "Shapes", flame),
    Item("crown", "Crown", "Shapes", crown),
    Item("arrow-right", "Arrow", "Arrows", arrow_right),
    Item("arrow-down", "Arrow down", "Arrows", arrow_down),
    Item("arrow-curved", "Curved arrow", "Arrows", arrow_curved),
    Item("chevrons", "Chevrons", "Arrows", chevrons),
    Item("speech", "Speech bubble", "Callouts", speech),
    Item("thought", "Thought bubble", "Callouts", thought),
    Item("circle-mark", "Circle", "Callouts", circle_mark),
    Item("underline", "Underline", "Callouts", underline),
    Item("check", "Check", "Callouts", check),
    Item("cross", "Cross", "Callouts", cross),
    Item("exclamation", "Warning", "Callouts", exclamation),
    Item("question", "Question", "Callouts", question),
    Item("new", "New", "Labels", new),
    Item("sale", "Sale", "Labels", sale),
    Item("live", "Live", "Labels", live),
    Item("wow", "Wow", "Labels", wow),
    Item("follow", "Follow", "Labels", follow),
    Item("smile", "Smile", "Faces", smile),
    Item("wink", "Wink", "Faces", wink),
    Item("laugh", "Laugh", "Faces", laugh),
    Item("surprised", "Surprised", "Faces", surprised),
    Item("heart-eyes", "Heart eyes", "Faces", heart_eyes),
    Item("cool", "Cool", "Faces", cool),
    Item("music-note", "Music note", "Icons", music_note),
    Item("bell", "Bell", "Icons", bell),
    Item("pin", "Pin", "Icons", pin),
]


# Sound effects ---------------------------------------------------------------


def _time(seconds: float, rate: int = SOUND_RATE) -> np.ndarray:
    return np.arange(round(seconds * rate)) / rate


def _noise(count: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(count)


def _bright(signal: np.ndarray) -> np.ndarray:
    """A first-difference high-pass: keeps the hiss, drops the rumble."""
    return np.diff(signal, prepend=0.0)


def _soft(signal: np.ndarray, width: int) -> np.ndarray:
    """A moving-average low-pass."""
    return np.convolve(signal, np.ones(width) / width, mode="same")


def _band(signal: np.ndarray, centres: np.ndarray, q: float = 3.0, rate: int = SOUND_RATE) -> np.ndarray:
    """A band-pass whose centre moves with every sample: a state-variable filter."""
    low = band = 0.0
    damp = 1.0 / q
    out = np.empty_like(signal)
    tune = 2.0 * np.sin(np.pi * np.minimum(centres, rate / 6) / rate)
    for index in range(len(signal)):
        low += tune[index] * band
        high = signal[index] - low - damp * band
        band += tune[index] * high
        out[index] = band
    return out


def _sine(frequency, t: np.ndarray, rate: int = SOUND_RATE) -> np.ndarray:
    """A sine at a fixed or moving frequency."""
    if np.isscalar(frequency):
        return np.sin(2 * np.pi * frequency * t)
    return np.sin(2 * np.pi * np.cumsum(frequency) / rate)


def _square(frequency: float, t: np.ndarray) -> np.ndarray:
    return sum(np.sin(2 * np.pi * frequency * k * t) / k for k in (1, 3, 5, 7, 9))


def _bell(frequency: float, seconds: float) -> np.ndarray:
    t = _time(seconds)
    ring = [(1.0, 1.0, 1.2), (2.76, 0.5, 0.6), (5.40, 0.25, 0.35), (8.93, 0.1, 0.2)]
    return sum(level * np.sin(2 * np.pi * frequency * ratio * t) * np.exp(-t / decay) for ratio, level, decay in ring)


def _place(total: float, *parts: tuple[float, np.ndarray]) -> np.ndarray:
    out = np.zeros(round(total * SOUND_RATE))
    for at, sound in parts:
        start = round(at * SOUND_RATE)
        end = min(len(out), start + len(sound))
        out[start:end] += sound[: end - start]
    return out


def whoosh(seconds: float) -> np.ndarray:
    t = _time(seconds)
    shape = np.sin(np.pi * t / seconds)
    return _band(_noise(len(t), 11), 300 + 2600 * shape**2) * shape**1.5


def swoosh(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _band(_noise(len(t), 12), 800 * (4200 / 800) ** (t / seconds)) * np.sin(np.pi * t / seconds) ** 2


def riser(seconds: float) -> np.ndarray:
    t = _time(seconds)
    climb = (t / seconds) ** 2
    pitch = 110 * 8 ** (t / seconds)
    tone = sum(np.sin(2 * np.pi * np.cumsum(pitch * k) / SOUND_RATE) / k for k in range(1, 7))
    return (_band(_noise(len(t), 13), 200 * 25 ** (t / seconds)) + 0.25 * tone) * climb


def downlifter(seconds: float) -> np.ndarray:
    t = _time(seconds)
    fall = (1 - t / seconds) ** 1.5
    return (_band(_noise(len(t), 14), 5000 * (150 / 5000) ** (t / seconds)) + 0.5 * _sine(400 * (60 / 400) ** (t / seconds), t)) * fall


def pop(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _sine(300 + 700 * np.exp(-t / 0.012), t) * np.exp(-t / 0.03) * (1 - np.exp(-t / 0.001))


def click(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _bright(_noise(len(t), 15)) * np.exp(-t / 0.004)


def tick(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return (np.sin(2 * np.pi * 2400 * t) + 0.3 * np.sin(2 * np.pi * 4800 * t)) * np.exp(-t / 0.008)


def ding(seconds: float) -> np.ndarray:
    return _bell(1318.5, seconds)


def chime(seconds: float) -> np.ndarray:
    return _place(seconds, (0.0, _bell(1046.5, seconds)), (0.22, 0.8 * _bell(1568.0, seconds - 0.22)))


def success(seconds: float) -> np.ndarray:
    notes = [(0.0, 523.25), (0.09, 659.25), (0.18, 783.99), (0.27, 1046.5)]
    t = _time(0.7)
    pluck = lambda f: sum(np.sin(2 * np.pi * f * k * t) * 0.6**k for k in range(1, 5)) * np.exp(-t / 0.18)  # noqa: E731
    return _place(seconds, *[(at, pluck(frequency)) for at, frequency in notes])


def error(seconds: float) -> np.ndarray:
    t = _time(0.2)
    shape = np.minimum(1, t / 0.005) * np.minimum(1, (0.2 - t) / 0.02)
    return _place(seconds, (0.0, _square(220, t) * shape), (0.25, _square(185, t) * shape))


def coin(seconds: float) -> np.ndarray:
    first, second = _time(0.07), _time(seconds - 0.07)
    return np.concatenate([_square(987.77, first), _square(1318.5, second) * np.exp(-second / 0.12)])


def boom(seconds: float) -> np.ndarray:
    t = _time(seconds)
    body = _sine(38 + 50 * np.exp(-t / 0.08), t) * np.exp(-t / 0.6)
    thud = _soft(_noise(len(t), 16), 60) * np.exp(-t / 0.05) * 6
    return np.tanh(1.5 * (body + thud))


def heartbeat(seconds: float) -> np.ndarray:
    t = _time(0.35)
    thump = (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 30 * t)) * np.exp(-t / 0.09) * (1 - np.exp(-t / 0.004))
    return _place(seconds, (0.0, thump), (0.28, 0.7 * thump))


def glitch(seconds: float) -> np.ndarray:
    rng = np.random.default_rng(17)
    parts, at = [], 0.0
    while at < seconds - 0.06:
        length = float(rng.uniform(0.02, 0.06))
        t = _time(length)
        choice = int(rng.integers(0, 3))
        if choice == 0:
            parts.append((at, _square(float(rng.uniform(200, 2000)), t) * 0.5))
        elif choice == 1:
            parts.append((at, _noise(len(t), int(rng.integers(0, 1000))) * 0.4))
        at += length
    return _place(seconds, *parts)


def shutter(seconds: float) -> np.ndarray:
    t = _time(0.06)
    snap = _soft(_bright(_noise(len(t), 18)), 4) * np.exp(-t / 0.01)
    return _place(seconds, (0.0, snap), (0.12, 0.8 * snap))


def typewriter(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _bright(_noise(len(t), 19)) * np.exp(-t / 0.003) + 0.2 * np.sin(2 * np.pi * 3000 * t) * np.exp(-t / 0.02)


SOUNDS = [
    Item("whoosh", "Whoosh", "Whooshes", whoosh, 0.9),
    Item("swoosh", "Swoosh", "Whooshes", swoosh, 0.4),
    Item("riser", "Riser", "Whooshes", riser, 2.6),
    Item("downlifter", "Downlifter", "Whooshes", downlifter, 1.8),
    Item("pop", "Pop", "Interface", pop, 0.14),
    Item("click", "Click", "Interface", click, 0.035),
    Item("tick", "Tick", "Interface", tick, 0.06),
    Item("ding", "Ding", "Interface", ding, 1.4),
    Item("chime", "Chime", "Interface", chime, 1.8),
    Item("success", "Success", "Interface", success, 1.0),
    Item("error", "Error", "Interface", error, 0.5),
    Item("coin", "Coin", "Interface", coin, 0.55),
    Item("boom", "Boom", "Impacts", boom, 1.8),
    Item("heartbeat", "Heartbeat", "Impacts", heartbeat, 1.3),
    Item("glitch", "Glitch", "Impacts", glitch, 0.7),
    Item("shutter", "Camera shutter", "Everyday", shutter, 0.4),
    Item("typewriter", "Typewriter", "Everyday", typewriter, 0.09),
]


# Music -----------------------------------------------------------------------


def _hz(note: float) -> float:
    return 440.0 * 2 ** ((note - 69) / 12)


def _clock(seconds: float) -> np.ndarray:
    return np.arange(round(seconds * MUSIC_RATE)) / MUSIC_RATE


def _voice(note: float, seconds: float, partials, decay: float, attack: float = 0.004) -> np.ndarray:
    t = _clock(seconds)
    frequency = _hz(note)
    tone = sum(level * np.sin(2 * np.pi * frequency * number * t) for number, level in partials)
    return tone * np.minimum(1.0, t / attack) * np.exp(-t / decay) * np.clip((seconds - t) / 0.02, 0, 1)


KEYS = [(1, 1.0), (2, 0.4), (3, 0.15), (4, 0.06)]
PLUCK = [(1, 1.0), (2, 0.55), (3, 0.3), (4, 0.18), (5, 0.1), (6, 0.05)]
PIANO = [(1, 1.0), (2, 0.5), (3, 0.25), (4, 0.12), (5, 0.06)]
GLASS = [(1, 1.0), (2.76, 0.4), (5.4, 0.2)]


def _pad(note: float, seconds: float, attack: float = 0.6, release: float = 0.9, harmonics: int = 6) -> np.ndarray:
    t = _clock(seconds)
    tone = np.zeros_like(t)
    for detune in (-0.004, 0.004):
        frequency = _hz(note) * (1 + detune)
        for k in range(1, harmonics + 1):
            tone += np.sin(2 * np.pi * frequency * k * t + k * detune * 300) / k
    return tone / 2 * np.clip(np.minimum(t / attack, (seconds - t) / release), 0, 1)


def _bass(note: float, seconds: float, saw: bool = False) -> np.ndarray:
    t = _clock(seconds)
    frequency = _hz(note)
    partials = [(k, 1 / k) for k in range(1, 9)] if saw else [(1, 1.0), (2, 0.3), (3, 0.1)]
    tone = sum(level * np.sin(2 * np.pi * frequency * number * t) for number, level in partials)
    return tone * np.minimum(1, t / 0.005) * np.clip((seconds - t) / 0.05, 0, 1) * (0.7 + 0.3 * np.exp(-t / 0.2))


def _kick() -> np.ndarray:
    t = _clock(0.45)
    return np.sin(2 * np.pi * np.cumsum(45 + 80 * np.exp(-t / 0.045)) / MUSIC_RATE) * np.exp(-t / 0.28) * np.minimum(1, t / 0.002)


def _snare(seed: int, gate: float = 0.0) -> np.ndarray:
    t = _clock(0.3)
    body = 0.6 * np.sin(2 * np.pi * 185 * t) * np.exp(-t / 0.07)
    rattle = 0.5 * _bright(_noise(len(t), seed)) * np.exp(-t / (0.25 if gate else 0.11))
    hit = body + rattle
    return hit * (t < gate) if gate else hit


def _hat(seed: int, open_: bool = False) -> np.ndarray:
    t = _clock(0.25 if open_ else 0.07)
    return _bright(_noise(len(t), seed)) * np.exp(-t / (0.08 if open_ else 0.018)) * 0.35


def _clap(seed: int) -> np.ndarray:
    t = _clock(0.3)
    burst = _bright(_noise(len(t), seed))
    shape = sum(np.exp(-np.clip(t - at, 0, None) / 0.006) * (t >= at) for at in (0.0, 0.011, 0.022)) + 0.4 * np.exp(-t / 0.12)
    return burst * shape * 0.4


def _tom(note: float) -> np.ndarray:
    t = _clock(0.9)
    frequency = _hz(note) * (1 + 0.6 * np.exp(-t / 0.03))
    ring = np.sin(2 * np.pi * np.cumsum(frequency) / MUSIC_RATE) * np.exp(-t / 0.35)
    thud = 0.2 * _soft(_noise(len(t), int(note)), 30) * np.exp(-t / 0.04)
    return ring + thud


def _shaker(seed: int) -> np.ndarray:
    t = _clock(0.1)
    return _bright(_noise(len(t), seed)) * np.sin(np.pi * t / 0.1) ** 2 * 0.25


class Bus:
    """A stereo mix: sounds placed in time, panned, with an optional echo."""

    def __init__(self, seconds: float):
        self.audio = np.zeros((round(seconds * MUSIC_RATE), 2))

    def add(self, sound: np.ndarray, at: float, gain: float = 1.0, pan: float = 0.0) -> None:
        start = round(at * MUSIC_RATE)
        end = min(len(self.audio), start + len(sound))
        if end <= start:
            return
        angle = (pan + 1) * math.pi / 4
        piece = sound[: end - start] * gain
        self.audio[start:end, 0] += piece * math.cos(angle)
        self.audio[start:end, 1] += piece * math.sin(angle)

    def echo(self, seconds: float, feedback: float, level: float) -> Bus:
        delay = round(seconds * MUSIC_RATE)
        wet = np.zeros_like(self.audio)
        for tap in range(1, 6):
            shift = delay * tap
            if shift >= len(self.audio):
                break
            copy = self.audio[:-shift] * feedback**tap
            wet[shift:] += copy[:, ::-1] if tap % 2 else copy
        self.audio = self.audio + wet * level
        return self


def _master(*buses: Bus) -> np.ndarray:
    mix = sum(bus.audio for bus in buses)
    count = len(mix)
    fade_in, fade_out = round(0.02 * MUSIC_RATE), round(1.5 * MUSIC_RATE)
    mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    mix[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None] ** 2
    mix = np.tanh(mix * 1.1)
    peak = float(np.abs(mix).max()) or 1.0
    return mix / peak * 0.89 if count else mix


def _length(bpm: int, bars: int) -> tuple[float, float]:
    beat = 60 / bpm
    return beat, bars * 4 * beat + TAIL


def paper_lanterns(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[52, 55, 59, 62, 66], [45, 55, 61, 66], [50, 54, 57, 61, 64], [47, 54, 57, 62]]
    keys, low, drums = Bus(seconds), Bus(seconds), Bus(seconds)
    swing = 0.08 * beat
    for bar in range(bars):
        start = bar * 4 * beat
        chord = chords[bar % 4]
        for index, note in enumerate(chord):
            keys.add(_voice(note, 2.6, KEYS, 1.4), start + index * 0.018, 0.16, -0.3 + 0.15 * index)
            keys.add(_voice(note + 12 if index == len(chord) - 1 else note, 1.2, KEYS, 0.8), start + 2.5 * beat + swing, 0.08, 0.2)
        root = chord[0] - 12
        low.add(_bass(root, 1.5 * beat), start, 0.35)
        low.add(_bass(root, beat), start + 2.5 * beat + swing, 0.25)
        for hit in (0.0, 2.5):
            drums.add(_kick(), start + hit * beat + (swing if hit % 1 else 0), 0.45)
        for hit in (1, 3):
            drums.add(_snare(bar * 4 + hit), start + hit * beat, 0.22)
        for step in range(8):
            drums.add(_hat(bar * 8 + step), start + step * beat / 2 + (swing if step % 2 else 0), 0.07 if step % 2 else 0.1, 0.25)
    crackle = Bus(seconds)
    rng = np.random.default_rng(21)
    for at in np.sort(rng.uniform(0, seconds, int(seconds * 12))):
        crackle.add(_bright(_noise(40, int(at * 1000))) * np.exp(-np.arange(40) / 8), float(at), 0.05, float(rng.uniform(-0.7, 0.7)))
    return _master(keys.echo(0.75 * beat, 0.3, 0.3), low, drums, crackle)


def morning_commute(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]
    order = [0, 1, 2, 3, 2, 1, 0, 1, 2, 3, 2, 1, 0, 1, 2, 3]
    arp, pads, low, drums = Bus(seconds), Bus(seconds), Bus(seconds), Bus(seconds)
    for bar in range(bars):
        start = bar * 4 * beat
        chord = chords[bar % 4]
        notes = [*chord, chord[0] + 12]
        for step, pick in enumerate(order):
            arp.add(_voice(notes[pick] + 12, 0.3, PLUCK, 0.28), start + step * beat / 4, 0.1, 0.35 if step % 2 else -0.35)
        for note in chord:
            pads.add(_pad(note, 4 * beat + 0.4), start, 0.035)
        for step in range(8):
            low.add(_bass(chord[0] - 24, 0.4 * beat), start + step * beat / 2, 0.3 if step % 2 == 0 else 0.22)
        if 0 < bar < bars - 1:
            for hit in range(4):
                drums.add(_kick(), start + hit * beat, 0.5)
            for hit in (1, 3):
                drums.add(_clap(bar * 4 + hit), start + hit * beat, 0.9)
            for step in range(4):
                drums.add(_hat(bar * 4 + step, open_=bar % 2 == 1 and step == 3), start + (step + 0.5) * beat, 0.09, 0.3)
    return _master(arp.echo(0.75 * beat, 0.35, 0.25), pads, low, drums)


def low_tide(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[41, 53, 57, 60, 64], [36, 48, 55, 62, 64], [45, 52, 55, 60], [43, 50, 52, 59]]
    pads, glass = Bus(seconds), Bus(seconds)
    for pair in range(bars // 2):
        start = pair * 8 * beat
        chord = chords[pair % 4]
        for index, note in enumerate(chord):
            if index == 0:
                t = _clock(8 * beat + 1)
                drone = np.sin(2 * np.pi * _hz(note) * t) * np.clip(np.minimum(t / 0.8, (8 * beat + 1 - t) / 1.2), 0, 1)
                pads.add(drone, start, 0.12)
            else:
                pads.add(_pad(note, 8 * beat + 1.0, attack=1.5, release=1.8), start, 0.05, -0.5 + 0.3 * index)
    rng = np.random.default_rng(31)
    scale = [72, 74, 76, 79, 81, 84]
    for step in range(int(bars * 4 / 1.5)):
        if rng.uniform() < 0.7:
            glass.add(_voice(int(rng.choice(scale)), 2.0, GLASS, 1.6), step * 1.5 * beat, 0.08, float(rng.uniform(-0.6, 0.6)))
    return _master(pads, glass.echo(0.5, 0.45, 0.4))


def last_light(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[45, 52, 57, 60, 64], [41, 53, 57, 60, 65], [48, 55, 60, 64, 67], [43, 50, 55, 59, 62]]
    strings, drums, lines = Bus(seconds), Bus(seconds), Bus(seconds)
    for bar in range(bars):
        start = bar * 4 * beat
        chord = chords[bar % 4]
        for index, note in enumerate(chord):
            strings.add(_pad(note, 4 * beat + 0.8, attack=0.9, release=1.0, harmonics=8), start, 0.05, -0.4 + 0.2 * index)
        if bar % 4 == 0:
            drums.add(_tom(28), start, 0.6)
        if 2 <= bar < bars - 1:
            for hit, note in ((0, 40), (1.5, 45), (2, 40), (3, 43)):
                drums.add(_tom(note), start + hit * beat, 0.35, 0.2 if note == 45 else -0.2)
        if bar >= bars - 5 and bar < bars - 1:
            for step in range(8):
                drums.add(_tom(47), start + step * beat / 2, 0.15)
                lines.add(_voice([69, 72, 76, 72][step % 4], 0.35, PLUCK, 0.25), start + step * beat / 2, 0.09, 0.3)
    drums.add(_tom(28), (bars - 1) * 4 * beat, 0.8)
    drums.add(_snare(99), (bars - 1) * 4 * beat, 0.3)
    return _master(strings, drums, lines.echo(0.5 * beat, 0.35, 0.3))


def neon_avenue(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[57, 60, 64], [53, 57, 60], [55, 60, 64], [55, 59, 62]]
    bass, pads, arp, drums = Bus(seconds), Bus(seconds), Bus(seconds), Bus(seconds)
    for bar in range(bars):
        start = bar * 4 * beat
        chord = chords[bar % 4]
        for step in range(8):
            bass.add(_bass(chord[0] - (24 if step % 2 == 0 else 12), 0.45 * beat, saw=True), start + step * beat / 2, 0.16)
        for note in chord:
            pads.add(_pad(note, 4 * beat + 0.3, attack=0.3, release=0.5, harmonics=10), start, 0.03)
        notes = [*chord, chord[0] + 12]
        for step in range(16):
            lead = _voice(notes[step % 4] + 12, 0.2, [(k, 1 / k) for k in range(1, 9)], 0.15)
            arp.add(lead, start + step * beat / 4, 0.05, 0.3 if step % 2 else -0.3)
        if bar > 0:
            for hit in range(4):
                drums.add(_kick(), start + hit * beat, 0.5)
            for hit in (1, 3):
                drums.add(_snare(bar * 4 + hit, gate=0.18), start + hit * beat, 0.3)
            for step in range(8):
                drums.add(_hat(bar * 8 + step), start + step * beat / 2, 0.07, 0.2)
    return _master(bass, pads, arp.echo(0.75 * beat, 0.4, 0.3), drums)


def bright_idea(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[55, 59, 62, 67], [50, 54, 57, 62], [52, 55, 59, 64], [48, 52, 55, 60]]
    piano, low, drums = Bus(seconds), Bus(seconds), Bus(seconds)
    for bar in range(bars):
        start = bar * 4 * beat
        chord = chords[bar % 4]
        for step in range(4):
            for note in chord:
                piano.add(_voice(note, 0.5, PIANO, 0.35), start + (step + 0.5) * beat, 0.07, -0.15)
        for step in (0, 2):
            piano.add(_voice(chord[-1] + 12, 1.2, PIANO, 0.8), start + step * beat, 0.08, 0.2)
            low.add(_bass(chord[0] - 12, 1.9 * beat), start + step * beat, 0.3)
        if bar < bars - 1:
            for hit in (0, 2):
                drums.add(_kick(), start + hit * beat, 0.5)
            for hit in (1, 3):
                drums.add(_clap(bar * 4 + hit), start + hit * beat, 0.7)
            for step in range(16):
                drums.add(_shaker(bar * 16 + step), start + step * beat / 4, 0.6 if step % 2 else 0.35, 0.3)
    return _master(piano, low, drums)


def _track(item_id: str, name: str, mood: str, make: Callable, bpm: int, bars: int) -> Item:
    return Item(item_id, name, mood, lambda: make(bpm, bars), bars * 4 * 60 / bpm + TAIL, bpm)


MUSIC = [
    _track("paper-lanterns", "Paper Lanterns", "Calm", paper_lanterns, 72, 10),
    _track("morning-commute", "Morning Commute", "Upbeat", morning_commute, 118, 16),
    _track("low-tide", "Low Tide", "Calm", low_tide, 60, 8),
    _track("last-light", "Last Light", "Dramatic", last_light, 84, 12),
    _track("neon-avenue", "Neon Avenue", "Retro", neon_avenue, 100, 14),
    _track("bright-idea", "Bright Idea", "Upbeat", bright_idea, 110, 15),
]

KINDS = {"stickers": STICKERS, "sounds": SOUNDS, "music": MUSIC}


# Rendering and routes ----------------------------------------------------------


def _write_wav(path: Path, audio: np.ndarray, rate: int) -> None:
    samples = np.clip(audio, -1, 1)
    channels = 1 if samples.ndim == 1 else samples.shape[1]
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes((samples * 32767).astype("<i2").tobytes())


def _sound(item: Item) -> np.ndarray:
    audio = np.asarray(item.make(item.seconds), dtype=np.float64)
    peak = float(np.abs(audio).max()) or 1.0
    audio = audio / peak * 0.89
    edge = min(len(audio) // 4, round(0.0005 * SOUND_RATE))
    audio[:edge] *= np.linspace(0, 1, edge)
    audio[-edge * 4 :] *= np.linspace(1, 0, edge * 4)
    return audio


def find(kind: str, item_id: str) -> Item:
    for item in KINDS.get(kind, []):
        if item.id == item_id:
            return item
    raise HTTPException(404, f"no {kind} item {item_id}")


def _folder(kind: str) -> Path:
    folder = LIBRARY_DIR / kind
    stamp = folder / ".version"
    if not stamp.exists() or stamp.read_text() != VERSION:
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        stamp.write_text(VERSION)
    return folder


def render(kind: str, item_id: str) -> Path:
    """The item's file, made on first request and kept."""
    item = find(kind, item_id)
    with _lock:
        folder = _folder(kind)
        for known in folder.glob(f"{item.id}.*"):
            return known
        if kind == "stickers":
            path = folder / f"{item.id}.png"
            _finish(item.make()).save(path)
            return path
        if kind == "sounds":
            path = folder / f"{item.id}.wav"
            _write_wav(path, _sound(item), SOUND_RATE)
            return path
        with tempfile.TemporaryDirectory(prefix="formcut-music-") as scratch:
            raw = Path(scratch) / f"{item.id}.wav"
            _write_wav(raw, item.make(), MUSIC_RATE)
            program = shutil.which("ffmpeg")
            if program:
                path = folder / f"{item.id}.m4a"
                command = [program, "-v", "error", "-y", "-i", str(raw), "-c:a", "aac", "-b:a", "192k", str(path)]
                done = subprocess.run(command, capture_output=True, check=False)
                if done.returncode == 0:
                    return path
                path.unlink(missing_ok=True)
            path = folder / f"{item.id}.wav"
            shutil.move(str(raw), path)
            return path


def describe(kind: str, item: Item) -> dict:
    entry = {"id": item.id, "name": item.name, "category": item.category, "url": f"/api/library/{kind}/{item.id}/file"}
    if item.seconds:
        entry["seconds"] = round(item.seconds, 3)
    if item.bpm:
        entry["bpm"] = item.bpm
    return entry


@router.get("/{kind}")
def catalogue(kind: str) -> dict:
    if kind not in KINDS:
        raise HTTPException(404, f"no library of {kind}")
    return {"kind": kind, "licence": LICENCE, "items": [describe(kind, item) for item in KINDS[kind]]}


@router.get("/{kind}/{item_id}/file")
def item_file(kind: str, item_id: str) -> FileResponse:
    return FileResponse(render(kind, item_id))


@router.post("/{kind}/{item_id}/import")
def import_item(kind: str, item_id: str) -> dict:
    """Put a copy of the item in the media bin, where it is used like any other media."""
    item = find(kind, item_id)
    source = render(kind, item_id)
    with tempfile.TemporaryDirectory(prefix="formcut-library-") as scratch:
        copy = Path(scratch) / source.name
        shutil.copy2(source, copy)
        return media.ingest_path(copy, item.name, {"source": "formcut library", "licence": LICENCE})
