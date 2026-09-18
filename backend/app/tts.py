"""ElevenLabs text-to-speech for formcut.

Only one capability is needed, so this is a REST client over httpx rather than
the provider SDK: POST /v1/text-to-speech/{voice} with the xi-api-key header
returns mp3 bytes and GET /v1/voices lists voices. Key-gated, degrading to 503
with a clear message when no key is configured, as stock media does."""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from . import providers
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .media import ingest_path

router = APIRouter(prefix="/api/tts", tags=["tts"])

# Overridable for a proxy, a mirror or a local stub; see providers.base_for.
def _base() -> str:
    return providers.base_for("elevenlabs")
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"
DEFAULT_MODEL = "eleven_multilingual_v2"
_MISSING_KEY = "ElevenLabs API key not configured. Add it in Settings, AI providers, or set ELEVENLABS_API_KEY in .env."


def _key() -> str:
    # A key stored by the interface wins over the environment, so adding one in
    # Settings takes effect without restarting the engine.
    key = providers.key_for("elevenlabs")
    if not key:
        raise HTTPException(status_code=503, detail=_MISSING_KEY)
    return key


@router.get("/status")
def tts_status() -> dict[str, Any]:
    return {"elevenlabs": bool(providers.key_for("elevenlabs"))}


@router.get("/voices")
def voices() -> dict[str, Any]:
    key = _key()
    try:
        resp = httpx.get(f"{_base()}/v1/voices", headers={"xi-api-key": key}, timeout=30.0)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"ElevenLabs request failed: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"ElevenLabs {resp.status_code}")
    items = [{"id": v.get("voice_id"), "name": v.get("name"), "labels": v.get("labels", {})}
             for v in resp.json().get("voices", [])]
    return {"voices": items}


class SpeakBody(BaseModel):
    text: str
    voice_id: Optional[str] = None
    model_id: Optional[str] = None


@router.post("/speak", status_code=201)
def speak(body: SpeakBody) -> dict[str, Any]:
    key = _key()
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="text is limited to 2000 characters")
    voice = body.voice_id or DEFAULT_VOICE
    try:
        resp = httpx.post(
            f"{_base()}/v1/text-to-speech/{voice}",
            headers={"xi-api-key": key, "Content-Type": "application/json"},
            json={"text": text, "model_id": body.model_id or DEFAULT_MODEL},
            timeout=120.0,
        )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"ElevenLabs request failed: {e}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code,
                            detail=f"ElevenLabs {resp.status_code}: {resp.text[:150]}")
    tmp = Path(tempfile.gettempdir()) / f"formcut_tts_{uuid.uuid4().hex}.mp3"
    tmp.write_bytes(resp.content)
    label = "".join(ch for ch in text[:40] if ch.isalnum() or ch in " -_").strip() or "speech"
    return ingest_path(tmp, f"{label}.mp3", extra={"source": "tts", "voice": voice})
