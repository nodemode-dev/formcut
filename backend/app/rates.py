"""Project frame rates as exact rationals.

A project rate is a whole number from 1 to 120 or one of the four NTSC rates a camera set to NTSC records:
24000/1001 (23.976), 30000/1001 (29.97), 60000/1001 (59.94) and 120000/1001 (119.88). The document carries the rate
as a number, because the window's timecode and frame-step maths take one; a number within a hundredth of an NTSC
rate (29.97, 29.97002997...) or the text "30000/1001" means that rate exactly, and everything that names a rate to
ffmpeg, an encoder or a timeline file takes it from `exact` here, never from a rounded float.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction

LOW, HIGH = 1, 120
NTSC = tuple(Fraction(base * 1000, 1001) for base in (24, 30, 60, 120))
TOLERANCE = 0.01


RATIO = re.compile(r"(\d{1,6})(?:/(\d{1,6}))?")
DECIMAL = re.compile(r"\d{1,3}\.\d{1,6}")
MAX_TEXT = 13


def _from_text(value: str) -> float:
    """A rate written as text: digits, a ratio of digits or a short decimal; no sign, exponent, inf or nan, so text
    from a document, the API or an agent can never make Fraction build an enormous number."""
    text = value.strip()
    if len(text) > MAX_TEXT:
        raise ValueError("Invalid frame rate")
    ratio = RATIO.fullmatch(text)
    if ratio:
        numerator, denominator = int(ratio.group(1)), int(ratio.group(2) or 1)
        if denominator == 0:
            raise ValueError("Invalid frame rate")
        return numerator / denominator
    if DECIMAL.fullmatch(text):
        return float(text)
    raise ValueError("Invalid frame rate")


def _from_pair(value) -> float:
    """A rate carried as a num/den pair: {"num": 30000, "den": 1001} or [30000, 1001]."""
    pair = (value.get("num"), value.get("den")) if isinstance(value, dict) else tuple(value)
    if len(pair) != 2 or not all(isinstance(part, int) and not isinstance(part, bool) for part in pair):
        raise ValueError("Invalid frame rate")
    numerator, denominator = pair
    if not 0 < numerator < 10**6 or not 0 < denominator < 10**6:
        raise ValueError("Invalid frame rate")
    return numerator / denominator


def exact(value) -> Fraction:
    """The project rate `value` stands for, or ValueError when it is not one a project can have.

    Every input is bounded before any arithmetic: text by its pattern, an int by its range, a float by being finite.
    The result is snapped to a whole rate from 1 to 120 or one of the four NTSC ratios; nothing else is a project rate.
    """
    if isinstance(value, bool) or value is None:
        raise ValueError("Invalid frame rate")
    if isinstance(value, str):
        number = _from_text(value)
    elif isinstance(value, (dict, list, tuple)):
        number = _from_pair(value)
    elif isinstance(value, int):
        if not LOW <= value <= HIGH:
            raise ValueError("Invalid frame rate")
        return Fraction(value)
    elif isinstance(value, float):
        number = value
    elif isinstance(value, Fraction):
        if not 0 < value.denominator < 10**6 or not 0 < value.numerator < 10**9:
            raise ValueError("Invalid frame rate")
        number = value.numerator / value.denominator
    else:
        raise ValueError("Invalid frame rate")
    if not math.isfinite(number) or not LOW <= number <= HIGH + TOLERANCE:
        raise ValueError("Invalid frame rate")
    for rate in NTSC:
        if abs(number - float(rate)) < TOLERANCE:
            return rate
    if abs(number - round(number)) < 1e-9 and LOW <= round(number) <= HIGH:
        return Fraction(round(number))
    raise ValueError("Invalid frame rate")


def number(rate: Fraction) -> int | float:
    """The rate as the document carries it: an int when whole, else the nearest float to the exact ratio."""
    return rate.numerator if rate.denominator == 1 else rate.numerator / rate.denominator


def text(rate: Fraction) -> str:
    """The rate as ffmpeg and timeline files take it: "30" or "30000/1001"."""
    return str(rate.numerator) if rate.denominator == 1 else f"{rate.numerator}/{rate.denominator}"
