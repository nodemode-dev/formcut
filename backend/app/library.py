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


# More stickers: the same palette, canvas and finish as those above ------------

GREEN = (76, 200, 90, 255)
LEAF = (46, 160, 80, 255)
PINK = (255, 128, 190, 255)
SKY = (120, 190, 255, 255)
CLOUD = (214, 228, 246, 255)
BROWN = (150, 95, 60, 255)
CREAM = (255, 232, 196, 255)
GREY = (150, 156, 168, 255)
RED = (230, 57, 70, 255)
GOLD = (240, 170, 30, 255)


def _badge(text: str, fill, ink, size: int = 440, half: int = 820, height: int = 340) -> Image.Image:
    art, draw = _canvas()
    draw.rounded_rectangle((C - half, C - height, C + half, C + height), radius=height, fill=fill)
    _words(draw, C, C + 10, text, size, ink)
    return art


def _cloud(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float, fill) -> None:
    for x, y, r in ((-420, 120, 330), (0, -60, 460), (420, 120, 330), (-180, 170, 330), (200, 170, 330)):
        _disc(draw, cx + x * scale, cy + y * scale, r * scale, fill)
    draw.rectangle((cx - 420 * scale, cy + 120 * scale, cx + 420 * scale, cy + 450 * scale), fill=fill)


def _turned(art: Image.Image, degrees: float) -> Image.Image:
    return art.rotate(degrees, resample=Image.Resampling.BICUBIC)


def gem():
    art, draw = _canvas()
    top, belt, tip = C - 560, C - 180, C + 820
    draw.polygon([(C - 520, top), (C + 520, top), (C + 820, belt), (C, tip), (C - 820, belt)], fill=SKY)
    draw.polygon([(C - 520, top), (C + 520, top), (C + 820, belt), (C - 820, belt)], fill=(170, 215, 255, 255))
    for x in (-300, 300):
        _stroke(draw, [(C + x, belt), (C, tip)], 30, (80, 150, 230, 255))
    _stroke(draw, [(C - 820, belt), (C + 820, belt)], 30, (80, 150, 230, 255))
    return art


def burst():
    art, draw = _canvas()
    draw.polygon(_star(C, C, 880, 640, points=12), fill=CORAL)
    _disc(draw, C, C, 470, SUN)
    return art


def ring():
    art, draw = _canvas()
    _disc(draw, C, C, 820, VIOLET)
    _disc(draw, C, C, 470, CLEAR)
    return art


def hexagon():
    art, draw = _canvas()
    draw.polygon([(C + 840 * math.cos(math.radians(60 * i)), C + 840 * math.sin(math.radians(60 * i))) for i in range(6)], fill=TEAL)
    return art


def rainbow():
    art, draw = _canvas()
    for index, colour in enumerate((CORAL, ORANGE, SUN, GREEN, BLUE)):
        radius = 860 - index * 130
        draw.pieslice((C - radius, C + 300 - radius, C + radius, C + 300 + radius), start=180, end=360, fill=colour)
    draw.pieslice((C - 210, C + 90, C + 210, C + 510), start=180, end=360, fill=CLEAR)
    draw.rectangle((0, C + 300, S, S), fill=CLEAR)
    return art


def arrow_left():
    return arrow_right().transpose(Image.Transpose.FLIP_LEFT_RIGHT)


def arrow_up():
    return _turned(arrow_right(), 90)


def double_arrow():
    art, draw = _canvas()
    draw.rectangle((C - 520, C - 130, C + 520, C + 130), fill=CORAL)
    draw.polygon([(C - 880, C), (C - 440, C - 430), (C - 440, C + 430)], fill=CORAL)
    draw.polygon([(C + 880, C), (C + 440, C - 430), (C + 440, C + 430)], fill=CORAL)
    return art


def circular_arrow():
    art, draw = _canvas()
    draw.arc((C - 720, C - 720, C + 720, C + 720), start=-40, end=250, fill=TEAL, width=230)
    angle = math.radians(-40)
    ex, ey = C + 605 * math.cos(angle), C + 605 * math.sin(angle)
    draw.polygon([(ex - 330, ey - 60), (ex + 330, ey - 60), (ex, ey + 340)], fill=TEAL)
    return art


def pow_burst():
    art, draw = _canvas()
    points = []
    for index in range(28):
        radius = 880 if index % 2 == 0 else (560 if index % 4 == 1 else 640)
        angle = math.radians(-90 + index * 360 / 28)
        points.append((C + radius * math.cos(angle), C + radius * math.sin(angle)))
    draw.polygon(points, fill=SUN)
    _words(draw, C, C + 20, "POW!", 400, RED)
    return art


def plus():
    art, draw = _canvas()
    draw.rounded_rectangle((C - 230, C - 800, C + 230, C + 800), radius=120, fill=GREEN)
    draw.rounded_rectangle((C - 800, C - 230, C + 800, C + 230), radius=120, fill=GREEN)
    return art


def zigzag():
    art, draw = _canvas()
    _stroke(draw, [(C - 820 + i * 205, C + (-260 if i % 2 else 260)) for i in range(9)], 150, CORAL)
    return art


def hot():
    art, draw = _canvas()
    draw.polygon(_star(C, C, 860, 700, points=16), fill=RED)
    _words(draw, C, C + 20, "HOT", 520, SUN)
    return art


def free():
    return _badge("FREE", TEAL, PAPER)


def soon():
    return _badge("SOON", VIOLET, PAPER)


def deal():
    art, draw = _canvas()
    draw.polygon(_star(C, C, 860, 700, points=16), fill=ORANGE)
    _words(draw, C, C + 20, "DEAL", 420, PAPER)
    return art


def top():
    art, draw = _canvas()
    draw.polygon(_star(C, C + 40, 880, 420), fill=GOLD)
    _words(draw, C, C + 90, "TOP", 300, INK)
    return art


def omg():
    art, draw = _canvas()
    draw.polygon(_star(C, C, 880, 600, points=12), fill=SUN)
    _words(draw, C, C + 20, "OMG", 430, CORAL)
    return art


def lol():
    return _badge("LOL", PINK, PAPER, size=500)


def like():
    art, draw = _canvas()
    draw.rounded_rectangle((C - 840, C - 320, C + 840, C + 320), radius=320, fill=BLUE)
    draw.polygon(_heart(C - 480, C - 30, 250), fill=PAPER)
    _words(draw, C + 180, C + 10, "LIKE", 380, PAPER)
    return art


def subscribe():
    return _badge("SUBSCRIBE", RED, PAPER, size=250, half=860, height=260)


def sad():
    art, draw = _face()
    _eyes(draw)
    draw.arc((C - 380, C + 180, C + 380, C + 720), start=200, end=340, fill=INK, width=90)
    return art


def angry():
    art, draw = _canvas()
    _disc(draw, C, C, 820, CORAL)
    _eyes(draw, 80, 110)
    _stroke(draw, [(C - 520, C - 520), (C - 170, C - 380)], 90, INK)
    _stroke(draw, [(C + 520, C - 520), (C + 170, C - 380)], 90, INK)
    draw.arc((C - 380, C + 200, C + 380, C + 700), start=200, end=340, fill=INK, width=90)
    return art


def sleepy():
    art, draw = _face()
    for x in (C - 330, C + 330):
        draw.arc((x - 170, C - 360, x + 170, C - 160), start=20, end=160, fill=INK, width=70)
    draw.ellipse((C - 120, C + 250, C + 120, C + 450), fill=INK)
    _words(draw, C + 560, C - 620, "z", 360, BLUE)
    return art


def star_eyes():
    art, draw = _face()
    for x in (C - 330, C + 330):
        draw.polygon(_star(x, C - 260, 230, 100), fill=ORANGE)
    draw.pieslice((C - 470, C - 120, C + 470, C + 520), start=0, end=180, fill=INK)
    return art


def kiss():
    art, draw = _face()
    _eyes(draw)
    draw.arc((C - 160, C + 180, C + 100, C + 360), start=270, end=90, fill=INK, width=70)
    draw.arc((C - 160, C + 330, C + 100, C + 510), start=270, end=90, fill=INK, width=70)
    draw.polygon(_heart(C + 520, C + 360, 200), fill=CORAL)
    return art


def crying():
    art, draw = _face()
    _eyes(draw)
    for x in (C - 330, C + 330):
        draw.polygon([(x - 90, C - 60), (x + 90, C - 60), (x, C - 240)], fill=SKY)
        _disc(draw, x, C - 40, 95, SKY)
    draw.arc((C - 380, C + 220, C + 380, C + 720), start=200, end=340, fill=INK, width=90)
    return art


def neutral():
    art, draw = _face()
    _eyes(draw)
    _stroke(draw, [(C - 340, C + 360), (C + 340, C + 360)], 90, INK)
    return art


def play():
    art, draw = _canvas()
    _disc(draw, C, C, 820, RED)
    draw.polygon([(C - 250, C - 420), (C - 250, C + 420), (C + 460, C)], fill=PAPER)
    return art


def camera():
    art, draw = _canvas()
    draw.rounded_rectangle((C - 330, C - 600, C + 330, C - 300), radius=90, fill=INK)
    draw.rounded_rectangle((C - 820, C - 420, C + 820, C + 620), radius=180, fill=INK)
    _disc(draw, C, C + 100, 400, GREY)
    _disc(draw, C, C + 100, 280, SKY)
    _disc(draw, C + 560, C - 210, 80, SUN)
    return art


def microphone():
    art, draw = _canvas()
    draw.rounded_rectangle((C - 290, C - 840, C + 290, C + 200), radius=290, fill=GREY)
    for y in range(-640, 120, 160):
        _stroke(draw, [(C - 180, C + y), (C + 180, C + y)], 26, (120, 126, 138, 255))
    draw.arc((C - 470, C - 220, C + 470, C + 460), start=0, end=180, fill=INK, width=90)
    draw.rectangle((C - 45, C + 440, C + 45, C + 700), fill=INK)
    draw.rounded_rectangle((C - 360, C + 680, C + 360, C + 780), radius=50, fill=INK)
    return art


def clock():
    art, draw = _canvas()
    _disc(draw, C, C, 820, SUN)
    _disc(draw, C, C, 650, CREAM)
    for hour in range(12):
        angle = math.radians(hour * 30)
        _disc(draw, C + 540 * math.sin(angle), C - 540 * math.cos(angle), 40 if hour % 3 else 60, INK)
    _stroke(draw, [(C, C), (C, C - 400)], 80, INK)
    _stroke(draw, [(C, C), (C + 300, C + 110)], 80, INK)
    _disc(draw, C, C, 80, CORAL)
    return art


def gift():
    art, draw = _canvas()
    draw.rectangle((C - 700, C - 160, C + 700, C + 800), fill=CORAL)
    draw.rectangle((C - 800, C - 400, C + 800, C - 120), fill=(235, 70, 78, 255))
    draw.rectangle((C - 110, C - 400, C + 110, C + 800), fill=SUN)
    for side in (-1, 1):
        draw.ellipse((C + side * 380 - 280, C - 760, C + side * 380 + 280, C - 400), fill=SUN)
        draw.ellipse((C + side * 380 - 130, C - 650, C + side * 380 + 130, C - 510), fill=CLEAR)
    return art


def trophy():
    art, draw = _canvas()
    for side in (-1, 1):
        draw.ellipse((C + side * 560 - 260, C - 620, C + side * 560 + 260, C - 60), fill=GOLD)
        draw.ellipse((C + side * 560 - 140, C - 500, C + side * 560 + 140, C - 180), fill=CLEAR)
    draw.pieslice((C - 520, C - 1100, C + 520, C + 180), start=0, end=180, fill=GOLD)
    draw.rectangle((C - 520, C - 680, C + 520, C - 460), fill=GOLD)
    draw.rectangle((C - 110, C + 150, C + 110, C + 520), fill=GOLD)
    draw.rounded_rectangle((C - 440, C + 500, C + 440, C + 760), radius=60, fill=BROWN)
    draw.polygon(_star(C, C - 330, 200, 85), fill=SUN)
    return art


def light_bulb():
    art, draw = _canvas()
    _disc(draw, C, C - 170, 560, SUN)
    draw.polygon([(C - 400, C + 200), (C + 400, C + 200), (C + 240, C + 480), (C - 240, C + 480)], fill=SUN)
    draw.rounded_rectangle((C - 260, C + 470, C + 260, C + 780), radius=60, fill=GREY)
    for y in (560, 660):
        _stroke(draw, [(C - 230, C + y), (C + 230, C + y)], 30, (120, 126, 138, 255))
    _stroke(draw, [(C - 150, C + 60), (C, C - 160), (C + 150, C + 60)], 50, ORANGE)
    return art


def lock():
    art, draw = _canvas()
    draw.arc((C - 430, C - 830, C + 430, C + 30), start=180, end=360, fill=GREY, width=170)
    draw.rectangle((C - 430 + 0, C - 400, C - 260, C - 50), fill=GREY)
    draw.rectangle((C + 260, C - 400, C + 430, C - 50), fill=GREY)
    draw.rounded_rectangle((C - 700, C - 100, C + 700, C + 800), radius=140, fill=SUN)
    _disc(draw, C, C + 280, 130, INK)
    draw.rectangle((C - 55, C + 280, C + 55, C + 560), fill=INK)
    return art


def sun():
    art, draw = _canvas()
    for index in range(12):
        angle = math.radians(index * 30)
        tip = (C + 880 * math.cos(angle), C + 880 * math.sin(angle))
        side = math.radians(index * 30 + 90)
        base = (C + 560 * math.cos(angle), C + 560 * math.sin(angle))
        draw.polygon(
            [
                tip,
                (base[0] + 130 * math.cos(side), base[1] + 130 * math.sin(side)),
                (base[0] - 130 * math.cos(side), base[1] - 130 * math.sin(side)),
            ],
            fill=ORANGE,
        )
    _disc(draw, C, C, 520, SUN)
    return art


def cloud():
    art, draw = _canvas()
    _cloud(draw, C, C - 120, 1.0, CLOUD)
    return art


def rain():
    art, draw = _canvas()
    _cloud(draw, C, C - 420, 0.9, CLOUD)
    for x, y in ((-420, 300), (0, 420), (420, 300), (-210, 640), (210, 640)):
        draw.polygon([(C + x - 90, C + y), (C + x + 90, C + y), (C + x, C + y - 200)], fill=BLUE)
        _disc(draw, C + x, C + y + 10, 95, BLUE)
    return art


def snowflake():
    art, draw = _canvas()
    for index in range(6):
        angle = math.radians(index * 60 - 90)
        end = (C + 820 * math.cos(angle), C + 820 * math.sin(angle))
        _stroke(draw, [(C, C), end], 110, SKY)
        for along, reach in ((0.55, 260), (0.8, 180)):
            px, py = C + 820 * along * math.cos(angle), C + 820 * along * math.sin(angle)
            for turn in (-40, 40):
                branch = angle + math.radians(turn)
                _stroke(draw, [(px, py), (px + reach * math.cos(branch), py + reach * math.sin(branch))], 80, SKY)
    return art


def moon():
    art, draw = _canvas()
    _disc(draw, C, C, 800, SUN)
    _disc(draw, C + 380, C - 260, 680, CLEAR)
    for x, y in ((380, 320), (560, -80)):
        draw.polygon(_star(C + x, C + y, 120, 50, points=4), fill=SUN)
    return art


def balloon():
    art, draw = _canvas()
    draw.ellipse((C - 560, C - 880, C + 560, C + 400), fill=CORAL)
    draw.ellipse((C - 330, C - 700, C - 120, C - 440), fill=(255, 150, 150, 255))
    draw.polygon([(C - 110, C + 480), (C + 110, C + 480), (C, C + 380)], fill=CORAL)
    draw.line([(C, C + 480), (C - 120, C + 620), (C + 80, C + 760), (C - 40, C + 880)], fill=INK, width=30, joint="curve")
    return art


def confetti():
    art, draw = _canvas()
    colours = (CORAL, SUN, TEAL, BLUE, VIOLET, PINK, ORANGE, GREEN)
    spots = (
        (-600, -560),
        (-120, -700),
        (380, -600),
        (680, -250),
        (-700, -100),
        (-300, -250),
        (200, -200),
        (600, 200),
        (-560, 350),
        (-120, 150),
        (300, 420),
        (-300, 620),
        (100, 700),
        (560, 640),
        (-720, 620),
        (720, -620),
    )
    for index, (x, y) in enumerate(spots):
        colour = colours[index % len(colours)]
        if index % 3 == 0:
            _disc(draw, C + x, C + y, 90, colour)
        else:
            angle = math.radians(index * 37)
            dx, dy = 150 * math.cos(angle), 150 * math.sin(angle)
            _stroke(draw, [(C + x - dx, C + y - dy), (C + x + dx, C + y + dy)], 90, colour)
    return art


def party_popper():
    art, draw = _canvas()
    draw.polygon([(C - 780, C + 780), (C - 60, C - 60), (C + 260, C + 260)], fill=VIOLET)
    for along in (0.35, 0.6):
        ax, ay = C - 780 + (C - 60 - (C - 780)) * along, C + 780 + (C - 60 - (C + 780)) * along
        bx, by = C - 780 + (C + 260 - (C - 780)) * along, C + 780 + (C + 260 - (C + 780)) * along
        _stroke(draw, [(ax, ay), (bx, by)], 70, SUN)
    for index, (x, y) in enumerate(((150, -620), (520, -520), (640, -150), (330, -330), (-120, -760), (760, 200))):
        colour = (CORAL, TEAL, SUN, BLUE, PINK, ORANGE)[index]
        _stroke(draw, [(C + x - 90, C + y + 60), (C + x + 90, C + y - 60)], 90, colour)
    return art


def firework():
    art, draw = _canvas()
    colours = (CORAL, SUN, TEAL, PINK, BLUE, ORANGE)
    for index in range(16):
        angle = math.radians(index * 22.5)
        start, end = 260, 820 if index % 2 == 0 else 640
        _stroke(
            draw,
            [(C + start * math.cos(angle), C + start * math.sin(angle)), (C + end * math.cos(angle), C + end * math.sin(angle))],
            80,
            colours[index % len(colours)],
        )
    draw.polygon(_star(C, C, 200, 80, points=4), fill=SUN)
    return art


def cake():
    art, draw = _canvas()
    draw.rounded_rectangle((C - 760, C + 60, C + 760, C + 760), radius=90, fill=PINK)
    draw.rounded_rectangle((C - 580, C - 330, C + 580, C + 120), radius=80, fill=CREAM)
    for x in range(-560, 600, 280):
        _disc(draw, C + x, C + 60, 120, (255, 255, 255, 255))
    draw.rectangle((C - 60, C - 700, C + 60, C - 330), fill=SKY)
    draw.polygon([(C - 90, C - 720), (C + 90, C - 720), (C, C - 920)], fill=ORANGE)
    return art


def leaf():
    art, draw = _canvas()
    body = Image.new("RGBA", (S, S), CLEAR)
    ImageDraw.Draw(body).ellipse((C - 460, C - 860, C + 460, C + 860), fill=GREEN)
    shape = _turned(body, -35)
    draw.bitmap((0, 0), shape.split()[3], fill=GREEN)
    _stroke(draw, [(C - 470, C + 680), (C + 420, C - 640)], 60, LEAF)
    return art


def flower():
    art, draw = _canvas()
    for index in range(6):
        angle = math.radians(index * 60)
        _disc(draw, C + 460 * math.cos(angle), C + 460 * math.sin(angle), 360, PINK)
    _disc(draw, C, C, 330, SUN)
    return art


def tree():
    art, draw = _canvas()
    draw.rectangle((C - 120, C + 420, C + 120, C + 860), fill=BROWN)
    for top_y, half, base_y in ((-880, 360, -300), (-560, 560, 120), (-220, 760, 520)):
        draw.polygon([(C, C + top_y), (C + half, C + base_y), (C - half, C + base_y)], fill=GREEN if top_y != -560 else LEAF)
    return art


def drop():
    art, draw = _canvas()
    _disc(draw, C, C + 240, 580, BLUE)
    draw.polygon([(C - 500, C - 50), (C + 500, C - 50), (C, C - 880)], fill=BLUE)
    draw.ellipse((C - 330, C + 100, C - 150, C + 380), fill=SKY)
    return art


def coffee():
    art, draw = _canvas()
    draw.arc((C + 280, C - 120, C + 820, C + 380), start=-90, end=90, fill=CREAM, width=120)
    draw.rounded_rectangle((C - 700, C - 300, C + 460, C + 620), radius=180, fill=CREAM)
    draw.rectangle((C - 700, C - 300, C + 460, C - 120), fill=BROWN)
    for x in (-420, -120, 180):
        draw.line(
            [(C + x, C - 420), (C + x + 70, C - 560), (C + x - 20, C - 700), (C + x + 60, C - 840)], fill=GREY, width=60, joint="curve"
        )
    return art


def pizza():
    art, draw = _canvas()
    draw.polygon([(C, C + 860), (C - 760, C - 520), (C + 760, C - 520)], fill=SUN)
    draw.rounded_rectangle((C - 840, C - 740, C + 840, C - 460), radius=140, fill=ORANGE)
    for x, y in ((-260, -260), (240, -200), (-30, 140), (160, 420), (-230, 340)):
        _disc(draw, C + x, C + y, 110, RED)
    return art


def donut():
    art, draw = _canvas()
    _disc(draw, C, C, 820, BROWN)
    _disc(draw, C, C - 30, 740, PINK)
    colours = (SUN, TEAL, PAPER, BLUE, CORAL)
    for index in range(14):
        angle = math.radians(index * 360 / 14 + 10)
        radius = 470 if index % 2 else 590
        x, y = C + radius * math.cos(angle), C - 30 + radius * math.sin(angle)
        _stroke(
            draw,
            [(x - 50 * math.cos(angle + 1), y - 50 * math.sin(angle + 1)), (x + 50 * math.cos(angle + 1), y + 50 * math.sin(angle + 1))],
            55,
            colours[index % len(colours)],
        )
    _disc(draw, C, C, 270, CLEAR)
    return art


def ice_cream():
    art, draw = _canvas()
    # The waffle lines are drawn on the cone's own layer and cut to its shape.
    corners = [(C - 460, C - 60), (C + 460, C - 60), (C, C + 880)]
    cone = Image.new("RGBA", (S, S), CLEAR)
    cone_draw = ImageDraw.Draw(cone)
    cone_draw.polygon(corners, fill=ORANGE)
    for step in range(-4, 5):
        _stroke(cone_draw, [(C + step * 150 - 230, C - 60), (C + step * 150 + 140, C + 540)], 26, (220, 110, 20, 255))
        _stroke(cone_draw, [(C + step * 150 + 230, C - 60), (C + step * 150 - 140, C + 540)], 26, (220, 110, 20, 255))
    shape = Image.new("L", (S, S), 0)
    ImageDraw.Draw(shape).polygon(corners, fill=255)
    art.paste(cone, (0, 0), shape)
    _disc(draw, C, C - 380, 460, PINK)
    _disc(draw, C - 320, C - 170, 250, PINK)
    _disc(draw, C + 320, C - 170, 250, PINK)
    _disc(draw, C + 110, C - 720, 110, RED)
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
    Item("gem", "Gem", "Shapes", gem),
    Item("burst", "Burst", "Shapes", burst),
    Item("ring", "Ring", "Shapes", ring),
    Item("hexagon", "Hexagon", "Shapes", hexagon),
    Item("rainbow", "Rainbow", "Shapes", rainbow),
    Item("arrow-left", "Arrow left", "Arrows", arrow_left),
    Item("arrow-up", "Arrow up", "Arrows", arrow_up),
    Item("double-arrow", "Double arrow", "Arrows", double_arrow),
    Item("circular-arrow", "Circular arrow", "Arrows", circular_arrow),
    Item("pow", "Pow", "Callouts", pow_burst),
    Item("plus", "Plus", "Callouts", plus),
    Item("zigzag", "Zigzag", "Callouts", zigzag),
    Item("hot", "Hot", "Labels", hot),
    Item("free", "Free", "Labels", free),
    Item("soon", "Soon", "Labels", soon),
    Item("deal", "Deal", "Labels", deal),
    Item("top", "Top", "Labels", top),
    Item("omg", "OMG", "Labels", omg),
    Item("lol", "LOL", "Labels", lol),
    Item("like", "Like", "Labels", like),
    Item("subscribe", "Subscribe", "Labels", subscribe),
    Item("sad", "Sad", "Faces", sad),
    Item("angry", "Angry", "Faces", angry),
    Item("sleepy", "Sleepy", "Faces", sleepy),
    Item("star-eyes", "Star eyes", "Faces", star_eyes),
    Item("kiss", "Kiss", "Faces", kiss),
    Item("crying", "Crying", "Faces", crying),
    Item("neutral", "Neutral", "Faces", neutral),
    Item("play", "Play", "Icons", play),
    Item("camera", "Camera", "Icons", camera),
    Item("microphone", "Microphone", "Icons", microphone),
    Item("clock", "Clock", "Icons", clock),
    Item("gift", "Gift", "Icons", gift),
    Item("trophy", "Trophy", "Icons", trophy),
    Item("light-bulb", "Light bulb", "Icons", light_bulb),
    Item("lock", "Lock", "Icons", lock),
    Item("sun", "Sun", "Weather", sun),
    Item("cloud", "Cloud", "Weather", cloud),
    Item("rain", "Rain", "Weather", rain),
    Item("snowflake", "Snowflake", "Weather", snowflake),
    Item("moon", "Moon", "Weather", moon),
    Item("balloon", "Balloon", "Celebration", balloon),
    Item("confetti", "Confetti", "Celebration", confetti),
    Item("party-popper", "Party popper", "Celebration", party_popper),
    Item("firework", "Firework", "Celebration", firework),
    Item("cake", "Cake", "Celebration", cake),
    Item("leaf", "Leaf", "Nature", leaf),
    Item("flower", "Flower", "Nature", flower),
    Item("tree", "Tree", "Nature", tree),
    Item("drop", "Drop", "Nature", drop),
    Item("coffee", "Coffee", "Food", coffee),
    Item("pizza", "Pizza", "Food", pizza),
    Item("donut", "Donut", "Food", donut),
    Item("ice-cream", "Ice cream", "Food", ice_cream),
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


# More sound effects: the same kit, each with its own seed ---------------------


def _shape(signal: np.ndarray, low: float = 0.0, high: float = 0.0) -> np.ndarray:
    """Keep what lies between low and high (Hz), with an eighth-order roll-off either
    side. The moving average and the band-pass above roll off too gently to make
    noise dark: white noise's highs leak through and it stays a hiss."""
    spectrum = np.fft.rfft(signal)
    freqs = np.fft.rfftfreq(len(signal), 1 / SOUND_RATE)
    gain = np.ones_like(freqs)
    if high:
        gain /= np.sqrt(1 + (freqs / high) ** 8)
    if low:
        gain *= 1 - 1 / np.sqrt(1 + (np.maximum(freqs, 1e-9) / low) ** 8)
    return np.fft.irfft(spectrum * gain, n=len(signal))


def _saw(frequency: float, t: np.ndarray, partials: int = 24) -> np.ndarray:
    return sum(np.sin(2 * np.pi * frequency * k * t) / k for k in range(1, partials + 1))


def _hit(seconds: float, seed: int, low: float, decay: float) -> np.ndarray:
    t = _time(seconds)
    body = _sine(low + 90 * np.exp(-t / 0.03), t) * np.exp(-t / decay)
    crack = _bright(_noise(len(t), seed)) * np.exp(-t / 0.012)
    return body + 0.6 * crack


def whoosh_short(seconds: float) -> np.ndarray:
    t = _time(seconds)
    shape = np.sin(np.pi * t / seconds)
    return _band(_noise(len(t), 21), 500 + 3800 * shape**2) * shape**2


def whoosh_long(seconds: float) -> np.ndarray:
    t = _time(seconds)
    shape = np.sin(np.pi * t / seconds)
    return _band(_noise(len(t), 22), 200 + 1800 * shape**3, q=2.2) * shape**1.2


def sweep_up(seconds: float) -> np.ndarray:
    t = _time(seconds)
    pitch = 200 * 16 ** (t / seconds)
    return _sine(pitch, t) * np.sin(np.pi * t / seconds) ** 0.8


def reverse_cymbal(seconds: float) -> np.ndarray:
    t = _time(seconds)
    swell = (t / seconds) ** 3
    return _band(_bright(_noise(len(t), 23)), 6000 + 2000 * swell, q=1.2) * swell


def notification(seconds: float) -> np.ndarray:
    return _place(seconds, (0.0, 0.8 * _bell(880.0, seconds)), (0.12, _bell(1318.5, seconds - 0.12)))


def _blip(start: float, end: float, seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _sine(start * (end / start) ** (t / seconds), t) * np.exp(-t / (seconds / 3)) * (1 - np.exp(-t / 0.002))


def toggle_on(seconds: float) -> np.ndarray:
    return _blip(600, 1200, seconds)


def toggle_off(seconds: float) -> np.ndarray:
    return _blip(1200, 600, seconds)


def send(seconds: float) -> np.ndarray:
    return _place(seconds, (0.0, 0.6 * whoosh_short(0.22)), (0.16, _blip(900, 1800, seconds - 0.16)))


def key_tap(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _soft(_bright(_noise(len(t), 24)), 3) * np.exp(-t / 0.006) + 0.3 * np.sin(2 * np.pi * 1800 * t) * np.exp(-t / 0.01)


def beep(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return np.sin(2 * np.pi * 1000 * t) * np.minimum(1, t / 0.005) * np.minimum(1, (seconds - t) / 0.01)


def countdown(seconds: float) -> np.ndarray:
    short = beep(0.12)
    t = _time(0.6)
    long = np.sin(2 * np.pi * 1500 * t) * np.minimum(1, t / 0.005) * np.minimum(1, (0.6 - t) / 0.05)
    return _place(seconds, (0.0, short), (1.0, short), (2.0, short), (3.0, long))


def level_up(seconds: float) -> np.ndarray:
    notes = (523.25, 659.25, 783.99, 1046.5, 1318.5)
    t = _time(0.12)
    parts = [(i * 0.08, _square(f, t) * np.exp(-t / 0.08) * 0.5) for i, f in enumerate(notes)]
    tail = _time(seconds - 0.4)
    parts.append((0.4, _square(1568.0, tail) * np.exp(-tail / 0.25) * 0.5))
    return _place(seconds, *parts)


def bubble(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _sine(400 + 1400 * (t / seconds) ** 0.6, t) * np.exp(-t / 0.05) * (1 - np.exp(-t / 0.002))


def hit(seconds: float) -> np.ndarray:
    return _hit(seconds, 25, 70, 0.12)


def thud(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _sine(45 + 40 * np.exp(-t / 0.05), t) * np.exp(-t / 0.2) + 0.4 * _soft(_noise(len(t), 26), 80) * np.exp(-t / 0.04)


def slam(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return np.tanh(2 * (_hit(seconds, 27, 60, 0.25) + 0.5 * _soft(_noise(len(t), 28), 20) * np.exp(-t / 0.15)))


def braam(seconds: float) -> np.ndarray:
    t = _time(seconds)
    swell = np.minimum(1, t / 0.25) * np.exp(-np.maximum(0, t - 0.4) / 1.2)
    chord = _saw(55.0, t) + 0.8 * _saw(82.41, t) + 0.5 * _saw(110.0, t)
    return np.tanh(0.6 * _soft(chord, 30) * swell) + 0.4 * _sine(41.2, t) * swell


def sub_drop(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _sine(120 * (30 / 120) ** (t / seconds), t) * (1 - t / seconds) ** 0.7


def rumble(seconds: float) -> np.ndarray:
    t = _time(seconds)
    shape = np.sin(np.pi * t / seconds) ** 0.7
    body = _shape(_noise(len(t), 29), high=120)
    return (body / (np.abs(body).max() or 1) + 0.35 * _sine(38, t)) * shape


def drum_roll(seconds: float) -> np.ndarray:
    parts, at, gap, index = [], 0.0, 0.09, 0
    while at < seconds - 0.4:
        t = _time(0.08)
        level = 0.3 + 0.7 * at / seconds
        parts.append((at, level * _bright(_noise(len(t), 30 + index)) * np.exp(-t / 0.02)))
        at += gap
        gap = max(0.035, gap * 0.97)
        index += 1
    t = _time(0.4)
    parts.append((seconds - 0.4, 1.4 * _bright(_noise(len(t), 99)) * np.exp(-t / 0.12) + _sine(60, t) * np.exp(-t / 0.15)))
    return _place(seconds, *parts)


def cymbal(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _band(_bright(_noise(len(t), 31)), 5500 + 0 * t, q=0.9) * np.exp(-t / 0.7) * (1 - np.exp(-t / 0.002))


def boing(seconds: float) -> np.ndarray:
    t = _time(seconds)
    pitch = 180 + 120 * np.sin(2 * np.pi * 9 * t) * np.exp(-t / 0.3) + 80 * np.exp(-t / 0.2)
    return _sine(pitch, t) * np.exp(-t / 0.35)


def slide_up(seconds: float) -> np.ndarray:
    t = _time(seconds)
    pitch = 500 * 4 ** (t / seconds) * (1 + 0.02 * np.sin(2 * np.pi * 6 * t))
    return (_sine(pitch, t) + 0.2 * _sine(pitch * 2, t)) * np.sin(np.pi * t / seconds) ** 0.4


def slide_down(seconds: float) -> np.ndarray:
    return slide_up(seconds)[::-1].copy()


def bonk(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return (np.sin(2 * np.pi * 720 * t) + 0.6 * np.sin(2 * np.pi * 1690 * t)) * np.exp(-t / 0.05) * (1 - np.exp(-t / 0.001))


def zip_up(seconds: float) -> np.ndarray:
    t = _time(seconds)
    return _band(_noise(len(t), 32), 1000 * 6 ** (t / seconds), q=6) * np.sin(np.pi * t / seconds)


def squeak(seconds: float) -> np.ndarray:
    t = _time(seconds)
    pitch = 1800 + 600 * np.sin(np.pi * t / seconds)
    return _sine(pitch, t) * np.sin(np.pi * t / seconds) ** 2


def applause(seconds: float) -> np.ndarray:
    rng = np.random.default_rng(33)
    clap = _time(0.03)
    parts = []
    for index in range(int(seconds * 60)):
        at = float(rng.uniform(0, seconds - 0.05))
        parts.append((at, float(rng.uniform(0.3, 1.0)) * _bright(_noise(len(clap), 1000 + index)) * np.exp(-clap / 0.008)))
    t = _time(seconds)
    return _place(seconds, *parts) * np.minimum(1, t / 0.4) * np.minimum(1, (seconds - t) / 0.8)


def knock(seconds: float) -> np.ndarray:
    t = _time(0.12)
    wood = _shape(_noise(len(t), 34), high=1500)
    wood = wood / (np.abs(wood).max() or 1)
    rap = (0.8 * wood + np.sin(2 * np.pi * 180 * t) + 0.5 * np.sin(2 * np.pi * 330 * t)) * np.exp(-t / 0.03) * (1 - np.exp(-t / 0.001))
    return _place(seconds, (0.0, rap), (0.22, 0.9 * rap), (0.44, rap))


def phone_buzz(seconds: float) -> np.ndarray:
    t = _time(0.4)
    buzz = np.tanh(3 * np.sin(2 * np.pi * 170 * t)) * np.minimum(1, t / 0.02) * np.minimum(1, (0.4 - t) / 0.02)
    return _place(seconds, (0.0, buzz), (0.6, buzz))


def cash_register(seconds: float) -> np.ndarray:
    t = _time(0.25)
    drawer = _soft(_noise(len(t), 35), 12) * np.exp(-t / 0.08) * 3
    return _place(seconds, (0.0, drawer), (0.12, _bell(2093.0, seconds - 0.12)), (0.14, 0.7 * _bell(2637.0, seconds - 0.14)))


def rain(seconds: float) -> np.ndarray:
    t = _time(seconds)
    hush = _soft(_bright(_noise(len(t), 36)), 6) * 0.5
    rng = np.random.default_rng(37)
    drop = _time(0.02)
    drops = [
        (
            float(rng.uniform(0, seconds - 0.03)),
            float(rng.uniform(0.2, 0.8)) * _sine(float(rng.uniform(1500, 4000)), drop) * np.exp(-drop / 0.004),
        )
        for _ in range(int(seconds * 40))
    ]
    return (hush + _place(seconds, *drops)) * np.minimum(1, t / 0.5) * np.minimum(1, (seconds - t) / 0.5)


def wind(seconds: float) -> np.ndarray:
    t = _time(seconds)
    gust = 0.55 + 0.45 * np.sin(2 * np.pi * 0.23 * t) * np.sin(2 * np.pi * 0.11 * t + 1)
    howl = _shape(_noise(len(t), 38), low=200, high=900)
    whistle = _shape(_noise(len(t), 41), low=700, high=1400) * gust**3
    return (howl * gust + 0.5 * whistle) * np.minimum(1, t / 1.0) * np.minimum(1, (seconds - t) / 1.0)


def waves(seconds: float) -> np.ndarray:
    t = _time(seconds)
    swell = (0.5 - 0.5 * np.cos(2 * np.pi * t / 4.0)) ** 2
    dark = _shape(_noise(len(t), 39), high=400)
    crash = _shape(_noise(len(t), 42), low=300, high=2500)
    dark, crash = dark / (np.abs(dark).max() or 1), crash / (np.abs(crash).max() or 1)
    return (0.35 + 0.4 * swell) * dark + swell**2 * crash


def crickets(seconds: float) -> np.ndarray:
    t = _time(seconds)
    # Smooth envelopes: a hard on and off clicks, and the clicks bury the chirp.
    trill = np.clip(np.sin(2 * np.pi * 30 * t) * 2 - 0.6, 0, 1) ** 2
    phrase = np.clip(np.sin(2 * np.pi * 1.1 * t) * 3 + 0.6, 0, 1)
    return np.sin(2 * np.pi * 4200 * t) * _soft(trill, 48) * phrase


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
    Item("whoosh-short", "Short whoosh", "Whooshes", whoosh_short, 0.35),
    Item("whoosh-long", "Long whoosh", "Whooshes", whoosh_long, 1.6),
    Item("sweep-up", "Sweep up", "Whooshes", sweep_up, 0.8),
    Item("reverse-cymbal", "Reverse cymbal", "Whooshes", reverse_cymbal, 2.0),
    Item("notification", "Notification", "Interface", notification, 1.2),
    Item("toggle-on", "Toggle on", "Interface", toggle_on, 0.12),
    Item("toggle-off", "Toggle off", "Interface", toggle_off, 0.12),
    Item("send", "Send", "Interface", send, 0.45),
    Item("key-tap", "Key tap", "Interface", key_tap, 0.05),
    Item("beep", "Beep", "Interface", beep, 0.25),
    Item("countdown", "Countdown", "Interface", countdown, 3.8),
    Item("level-up", "Level up", "Interface", level_up, 1.1),
    Item("bubble", "Bubble", "Interface", bubble, 0.16),
    Item("hit", "Hit", "Impacts", hit, 0.6),
    Item("thud", "Thud", "Impacts", thud, 0.8),
    Item("slam", "Slam", "Impacts", slam, 1.0),
    Item("braam", "Braam", "Impacts", braam, 3.0),
    Item("sub-drop", "Sub drop", "Impacts", sub_drop, 1.5),
    Item("rumble", "Rumble", "Impacts", rumble, 3.0),
    Item("drum-roll", "Drum roll", "Impacts", drum_roll, 2.5),
    Item("cymbal", "Cymbal crash", "Impacts", cymbal, 2.5),
    Item("boing", "Boing", "Cartoon", boing, 1.0),
    Item("slide-up", "Slide whistle up", "Cartoon", slide_up, 0.9),
    Item("slide-down", "Slide whistle down", "Cartoon", slide_down, 0.9),
    Item("bonk", "Bonk", "Cartoon", bonk, 0.3),
    Item("zip", "Zip", "Cartoon", zip_up, 0.35),
    Item("squeak", "Squeak", "Cartoon", squeak, 0.25),
    Item("applause", "Applause", "Everyday", applause, 4.0),
    Item("knock", "Door knock", "Everyday", knock, 0.7),
    Item("phone-buzz", "Phone buzz", "Everyday", phone_buzz, 1.1),
    Item("cash-register", "Cash register", "Everyday", cash_register, 1.4),
    Item("rain", "Rain", "Ambience", rain, 8.0),
    Item("wind", "Wind", "Ambience", wind, 8.0),
    Item("waves", "Waves", "Ambience", waves, 8.0),
    Item("crickets", "Crickets", "Ambience", crickets, 6.0),
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


# More music: the same instruments and mixer ------------------------------------

SQUARE = [(1, 1.0), (3, 0.33), (5, 0.2), (7, 0.14), (9, 0.11)]


def _808(note: float, seconds: float) -> np.ndarray:
    t = _clock(seconds)
    frequency = _hz(note) * (1 + 0.5 * np.exp(-t / 0.03))
    return np.tanh(1.6 * np.sin(2 * np.pi * np.cumsum(frequency) / MUSIC_RATE)) * np.exp(-t / 1.2) * np.clip((seconds - t) / 0.05, 0, 1)


def _chords_every_bar(bars: int, chords: list[list[int]]) -> list[list[int]]:
    return [chords[bar % len(chords)] for bar in range(bars)]


def sunday_porch(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[55, 59, 62, 67], [52, 55, 59, 64], [48, 52, 55, 60], [50, 54, 57, 62]]
    pluck, pad, low, perc = Bus(seconds), Bus(seconds), Bus(seconds), Bus(seconds)
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        pattern = [0, 1, 2, 3, 2, 1, 2, 3]
        for step, index in enumerate(pattern):
            pluck.add(_voice(chord[index] + 12, 1.2, PLUCK, 0.45), start + step * beat / 2, 0.14, -0.4 + 0.1 * index)
        pad.add(_pad(chord[0] + 12, 4 * beat + 0.4, attack=1.0), start, 0.05)
        low.add(_bass(chord[0] - 12, 2 * beat), start, 0.3)
        low.add(_bass(chord[2] - 12, 2 * beat), start + 2 * beat, 0.22)
        for step in range(8):
            perc.add(_shaker(bar * 8 + step), start + step * beat / 2, 0.18 if step % 2 else 0.1, 0.4)
    return _master(pluck.echo(0.75 * beat, 0.25, 0.25), pad, low, perc)


def glass_garden(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[57, 60, 64, 71], [53, 57, 60, 67], [48, 55, 60, 64], [55, 59, 62, 69]]
    bells, pad = Bus(seconds), Bus(seconds)
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        pad.add(_pad(chord[0], 4 * beat + 1.0, attack=1.5, release=1.5), start, 0.07, -0.2)
        pad.add(_pad(chord[2], 4 * beat + 1.0, attack=1.5, release=1.5), start, 0.05, 0.2)
        for step, index in enumerate([3, 1, 2, 0, 2, 3]):
            bells.add(_voice(chord[index] + 12, 2.4, GLASS, 1.1), start + step * beat * 2 / 3, 0.1, -0.6 + 0.24 * step)
    return _master(bells.echo(beat, 0.4, 0.4), pad)


def open_road(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[60, 64, 67], [55, 59, 62], [57, 60, 64], [53, 57, 60]]
    keys, low, drums = Bus(seconds), Bus(seconds), Bus(seconds)
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        for hit in range(4):
            drums.add(_kick(), start + hit * beat, 0.5)
            drums.add(_hat(bar * 16 + hit * 4 + 2, open_=True), start + (hit + 0.5) * beat, 0.12, 0.3)
        for hit in (1, 3):
            drums.add(_clap(bar * 2 + hit), start + hit * beat, 0.35)
        for step in range(8):
            note = chord[0] - 24 + (12 if step % 2 else 0)
            low.add(_bass(note, beat / 2 * 0.9, saw=True), start + step * beat / 2, 0.16)
        for hit in (0, 1.5, 2.5, 3.5):
            for index, note in enumerate(chord):
                keys.add(_voice(note, 0.5, PIANO, 0.3), start + hit * beat, 0.12, -0.2 + 0.2 * index)
    return _master(keys, low, drums)


def confetti_song(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[62, 66, 69], [59, 62, 66], [55, 59, 62], [57, 61, 64]]
    lead, pad, low, drums = Bus(seconds), Bus(seconds), Bus(seconds), Bus(seconds)
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        for step in range(16):
            note = chord[step % 3] + (12 if step % 4 == 3 else 0)
            lead.add(_voice(note + 12, 0.3, PLUCK, 0.12), start + step * beat / 4, 0.1, 0.3 if step % 2 else -0.3)
            drums.add(_hat(bar * 16 + step), start + step * beat / 4, 0.06 if step % 2 else 0.1)
        for hit in range(4):
            drums.add(_kick(), start + hit * beat, 0.5)
            pumped = _pad(chord[1], beat, attack=0.12, release=0.1)
            pad.add(pumped, start + hit * beat, 0.06)
            low.add(_bass(chord[0] - 24, beat * 0.8, saw=True), start + (hit + 0.5) * beat, 0.14)
        for hit in (1, 3):
            drums.add(_clap(bar * 4 + hit), start + hit * beat, 0.3)
    return _master(lead.echo(0.75 * beat, 0.25, 0.2), pad, low, drums)


def kick_push(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[57, 60, 64, 67], [53, 57, 60, 64], [50, 53, 57, 60], [52, 56, 59, 62]]
    keys, low, drums = Bus(seconds), Bus(seconds), Bus(seconds)
    swing = 0.1 * beat
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        for hit in (0.0, 1.75, 2.5):
            drums.add(_kick(), start + hit * beat + (swing if hit % 1 else 0), 0.55)
        for hit in (1, 3):
            drums.add(_snare(bar * 2 + hit), start + hit * beat, 0.35)
        for step in range(8):
            drums.add(_hat(bar * 8 + step), start + step * beat / 2 + (swing if step % 2 else 0), 0.08, 0.25)
        for index, note in enumerate(chord):
            keys.add(_voice(note, 3.2, PIANO, 1.6), start + index * 0.02, 0.1, -0.3 + 0.2 * index)
            keys.add(_voice(note, 0.8, PIANO, 0.4), start + 2.5 * beat + swing, 0.06, 0.2)
        low.add(_bass(chord[0] - 12, 1.5 * beat), start, 0.32)
        low.add(_bass(chord[0] - 12, beat), start + 2.5 * beat + swing, 0.25)
    return _master(keys.echo(0.5 * beat, 0.3, 0.25), low, drums)


def night_shift(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    roots = [45, 45, 41, 43]
    pad, low, drums = Bus(seconds), Bus(seconds), Bus(seconds)
    for bar in range(bars):
        start = bar * 4 * beat
        root = roots[bar % 4]
        pad.add(_pad(root + 24, 4 * beat + 0.5, attack=0.8), start, 0.16, -0.3)
        pad.add(_pad(root + 27, 4 * beat + 0.5, attack=0.8), start, 0.14, 0.3)
        low.add(_808(root - 12, 1.8 * beat), start, 0.4)
        low.add(_808(root - 12, beat), start + 2.75 * beat, 0.4)
        drums.add(_kick(), start, 0.4)
        drums.add(_kick(), start + 2.75 * beat, 0.35)
        drums.add(_clap(bar), start + 2 * beat, 0.4)
        drums.add(_snare(bar + 50), start + 2 * beat, 0.2)
        for step in range(16):
            drums.add(_hat(bar * 16 + step), start + step * beat / 4, 0.07 if step % 2 else 0.1, 0.2)
        if bar % 2 == 1:
            for roll in range(6):
                drums.add(_hat(bar * 100 + roll), start + 3 * beat + roll * beat / 6, 0.06, 0.2)
    return _master(pad, low, drums)


def pulse_lines(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[57, 60, 64], [53, 57, 60], [55, 59, 62], [52, 55, 59]]
    arp, low, drums = Bus(seconds), Bus(seconds), Bus(seconds)
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        for step in range(16):
            low.add(_bass(chord[0] - 24, beat / 4 * 0.8, saw=True), start + step * beat / 4, 0.10 if step % 4 else 0.13)
            arp.add(
                _voice(chord[step % 3] + 12 + (12 if step % 8 >= 4 else 0), 0.25, SQUARE, 0.1),
                start + step * beat / 4,
                0.16,
                -0.4 if step % 2 else 0.4,
            )
        for hit in range(4):
            drums.add(_kick(), start + hit * beat, 0.5)
            drums.add(_hat(bar * 4 + hit, open_=True), start + (hit + 0.5) * beat, 0.1, 0.3)
        drums.add(_clap(bar), start + beat, 0.25)
        drums.add(_clap(bar + 500), start + 3 * beat, 0.25)
    return _master(arp.echo(0.375 * beat, 0.35, 0.3), low, drums)


def deep_current(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[57, 60, 64, 67], [55, 59, 62, 65], [53, 57, 60, 64], [55, 58, 62, 65]]
    stabs, low, drums = Bus(seconds), Bus(seconds), Bus(seconds)
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        for hit in range(4):
            drums.add(_kick(), start + hit * beat, 0.55)
            drums.add(_hat(bar * 4 + hit, open_=True), start + (hit + 0.5) * beat, 0.16, 0.25)
        for hit in (1, 3):
            drums.add(_clap(bar * 3 + hit), start + hit * beat, 0.25, -0.1)
        for hit in (0.75, 2.25):
            for index, note in enumerate(chord):
                stabs.add(_voice(note, 0.3, KEYS, 0.12), start + hit * beat, 0.24, -0.2 + 0.13 * index)
        for step, offset in enumerate((0, 0.75, 1.5, 2.5, 3.25)):
            low.add(_bass(chord[0] - 24 + (7 if step == 3 else 0), beat * 0.6), start + offset * beat, 0.22)
    return _master(stabs.echo(0.75 * beat, 0.4, 0.35), low, drums)


def rising_tide(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    roots = [45, 41, 43, 40]
    toms, pad, low, hits = Bus(seconds), Bus(seconds), Bus(seconds), Bus(seconds)
    for bar in range(bars):
        start = bar * 4 * beat
        grow = 0.4 + 0.6 * bar / max(1, bars - 1)
        root = roots[bar % 4]
        for step in range(8):
            toms.add(
                _tom(root - (0 if step % 3 else 5)), start + step * beat / 2, (0.22 if step % 2 else 0.3) * grow, -0.3 if step % 2 else 0.3
            )
        pad.add(_pad(root + 12, 4 * beat + 0.4, attack=1.2), start, 0.16 * grow, -0.3)
        pad.add(_pad(root + 19, 4 * beat + 0.4, attack=1.2), start, 0.14 * grow, 0.3)
        low.add(_bass(root - 12, 4 * beat, saw=True), start, 0.14 * grow)
        if bar % 2 == 0:
            hits.add(_kick(), start, 0.5 * grow)
            hits.add(_bass(root - 24, 2 * beat, saw=True), start, 0.3 * grow)
    return _master(toms, pad, low, hits)


def last_stand(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[50, 53, 57], [46, 50, 53], [48, 51, 55], [45, 49, 52]]
    strings, low, toms = Bus(seconds), Bus(seconds), Bus(seconds)
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        for index, note in enumerate(chord):
            strings.add(_pad(note + 12, 4 * beat + 0.3, attack=0.4, harmonics=8), start, 0.05, -0.4 + 0.4 * index)
        for step in range(8):
            low.add(_bass(chord[0] - 12, beat / 2 * 0.7), start + step * beat / 2, 0.2 if step % 2 else 0.28)
        toms.add(_tom(chord[0] - 12), start, 0.4)
        toms.add(_tom(chord[0] - 17), start + 2.5 * beat, 0.3)
        if bar % 4 == 3:
            for roll in range(4):
                toms.add(_tom(chord[0] - 12 + roll), start + (3 + roll / 4) * beat, 0.25)
    return _master(strings.echo(beat, 0.2, 0.2), low, toms)


def arcade_heart(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[60, 64, 67], [57, 60, 64], [53, 57, 60], [55, 59, 62]]
    melody = [0, 2, 1, 2, 0, 1, 2, 1]
    lead, low, drums = Bus(seconds), Bus(seconds), Bus(seconds)
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        for step, index in enumerate(melody):
            lead.add(_voice(chord[index] + 12, beat / 2 * 0.85, SQUARE, 0.4, attack=0.002), start + step * beat / 2, 0.07, 0.1)
        for step in range(8):
            low.add(
                _voice(chord[0] - 12 + (12 if step % 2 else 0), beat / 2 * 0.8, SQUARE, 0.3, attack=0.002),
                start + step * beat / 2,
                0.08,
                -0.1,
            )
        for hit in (0, 2):
            drums.add(_kick(), start + hit * beat, 0.4)
        for hit in (1, 3):
            drums.add(_snare(bar * 2 + hit), start + hit * beat, 0.25)
        for step in range(8):
            drums.add(_hat(bar * 8 + step), start + step * beat / 2, 0.08)
    return _master(lead, low, drums)


def cassette_summer(bpm: int, bars: int) -> np.ndarray:
    beat, seconds = _length(bpm, bars)
    chords = [[57, 61, 64, 68], [54, 57, 61, 64], [52, 56, 59, 62], [50, 54, 57, 61]]
    pad, low, drums, keys = Bus(seconds), Bus(seconds), Bus(seconds), Bus(seconds)
    for bar, chord in enumerate(_chords_every_bar(bars, chords)):
        start = bar * 4 * beat
        for index, note in enumerate(chord):
            pad.add(_pad(note, 4 * beat + 0.2, attack=0.1, release=0.3, harmonics=9), start, 0.04, -0.3 + 0.2 * index)
        for step in range(8):
            low.add(_bass(chord[0] - 12, beat / 2 * 0.8, saw=True), start + step * beat / 2, 0.14)
        for hit in (0, 2, 2.5):
            drums.add(_kick(), start + hit * beat, 0.45)
        for hit in (1, 3):
            drums.add(_snare(bar * 2 + hit, gate=0.16), start + hit * beat, 0.4)
        for step in range(8):
            drums.add(_hat(bar * 8 + step), start + step * beat / 2, 0.07, 0.3)
        keys.add(_voice(chord[3] + 12, 0.6, PLUCK, 0.3), start + 3.5 * beat, 0.08, 0.4)
    return _master(pad, low, drums, keys.echo(0.75 * beat, 0.35, 0.3))


def _track(item_id: str, name: str, mood: str, make: Callable, bpm: int, bars: int) -> Item:
    return Item(item_id, name, mood, lambda: make(bpm, bars), bars * 4 * 60 / bpm + TAIL, bpm)


MUSIC = [
    _track("paper-lanterns", "Paper Lanterns", "Calm", paper_lanterns, 72, 10),
    _track("morning-commute", "Morning Commute", "Upbeat", morning_commute, 118, 16),
    _track("low-tide", "Low Tide", "Calm", low_tide, 60, 8),
    _track("last-light", "Last Light", "Dramatic", last_light, 84, 12),
    _track("neon-avenue", "Neon Avenue", "Retro", neon_avenue, 100, 14),
    _track("bright-idea", "Bright Idea", "Upbeat", bright_idea, 110, 15),
    _track("sunday-porch", "Sunday Porch", "Calm", sunday_porch, 80, 12),
    _track("glass-garden", "Glass Garden", "Calm", glass_garden, 66, 8),
    _track("open-road", "Open Road", "Upbeat", open_road, 124, 16),
    _track("confetti", "Confetti", "Upbeat", confetti_song, 128, 16),
    _track("kick-push", "Kick Push", "HipHop", kick_push, 90, 12),
    _track("night-shift", "Night Shift", "HipHop", night_shift, 76, 12),
    _track("pulse-lines", "Pulse Lines", "Electronic", pulse_lines, 122, 16),
    _track("deep-current", "Deep Current", "Electronic", deep_current, 118, 16),
    _track("rising-tide", "Rising Tide", "Dramatic", rising_tide, 90, 12),
    _track("last-stand", "Last Stand", "Dramatic", last_stand, 70, 10),
    _track("arcade-heart", "Arcade Heart", "Retro", arcade_heart, 140, 16),
    _track("cassette-summer", "Cassette Summer", "Retro", cassette_summer, 104, 12),
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


_item_locks: dict[tuple[str, str], threading.Lock] = {}


def _item_lock(kind: str, item_id: str) -> threading.Lock:
    with _lock:
        return _item_locks.setdefault((kind, item_id), threading.Lock())


def render(kind: str, item_id: str) -> Path:
    """The item's file, made on first request and kept.

    The folder is set up under the library's lock; each item then has its own,
    so different items are made at once (the drawing is OpenCV and NumPy, which
    release the interpreter lock) and one item is never made twice at once.
    """
    item = find(kind, item_id)
    with _lock:
        folder = _folder(kind)
    with _item_lock(kind, item.id):
        for known in folder.glob(f"{item.id}.*"):
            return known
        if kind == "stickers":
            path = folder / f"{item.id}.png"
            staged = folder / f".{item.id}.png.part"  # hidden from the glob above until it is whole
            _finish(item.make()).save(staged, format="PNG")
            staged.replace(path)
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


def warm_stickers() -> None:
    """Draw every sticker not yet drawn, on a background thread at startup.

    Each is drawn the first time it is asked for; with 86 that kept the Stickers
    tab blank for most of a minute on a first visit. render() caches and locks,
    so a sticker asked for meanwhile waits at most for the one being drawn.
    """
    import os
    from concurrent.futures import ThreadPoolExecutor

    def one(item: Item) -> None:
        try:
            render("stickers", item.id)
        except Exception:
            import logging

            logging.getLogger(__name__).debug("could not draw sticker %s ahead of time", item.id, exc_info=True)

    def run() -> None:
        with ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 2), thread_name_prefix="warm-sticker") as pool:
            list(pool.map(one, STICKERS))

    threading.Thread(target=run, name="warm-stickers", daemon=True).start()


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
