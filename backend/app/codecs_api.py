"""Settings, Advanced: H.264 through Cisco's OpenH264 (openh264.py).

The person turns its use on and off here, sees Cisco's notice beside the switch,
and can read the whole licence: conditions 2, 3 and 4 of Cisco's.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import encoders, openh264

router = APIRouter(prefix="/api/codecs", tags=["codecs"])


class Use(BaseModel):
    enabled: bool


def _state() -> dict:
    return {**openh264.status(), "needed": encoders.choose("h264") is None}


@router.get("/openh264")
def state() -> dict:
    return _state()


@router.post("/openh264")
def use(body: Use) -> dict:
    openh264.set_enabled(body.enabled)
    return _state()


@router.delete("/openh264")
def remove() -> dict:
    openh264.remove()
    return _state()


@router.get("/openh264/licence", response_class=PlainTextResponse)
def licence() -> str:
    return openh264.LICENCE
