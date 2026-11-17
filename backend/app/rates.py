"""Project frame rates as exact rationals.

A project rate is a whole number from 1 to 120 or one of the four NTSC rates a camera set to NTSC records:
24000/1001 (23.976), 30000/1001 (29.97), 60000/1001 (59.94) and 120000/1001 (119.88). The document carries the rate
as a number, because the window's timecode and frame-step maths take one; a number within a hundredth of an NTSC
rate (29.97, 29.97002997...) or the text "30000/1001" means that rate exactly, and everything that names a rate to
ffmpeg, an encoder or a timeline file takes it from `exact` here, never from a rounded float.
"""

from __future__ import annotations

import math
from fractions import Fraction

LOW, HIGH = 1, 120
NTSC = tuple(Fraction(base * 1000, 1001) for base in (24, 30, 60, 120))
TOLERANCE = 0.01


def exact(value) -> Fraction:
    """The project rate `value` stands for, or ValueError when it is not one a project can have."""
    if isinstance(value, bool):
        raise ValueError("Invalid frame rate")
    if isinstance(value, str):
        try:
            value = Fraction(value.strip())
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError("Invalid frame rate") from exc
    if isinstance(value, (Fraction, int, float)):
        number = float(value)
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
