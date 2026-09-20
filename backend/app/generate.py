"""Generative media (image, video, audio).

Generation goes through the same provider registry that stock and speech use,
so a key is stored once and the engine never puts it in a document or a log.
Every provider is declared as data: which purposes it serves, what it needs and
what it returns, so the interface can build its own controls from the reply
rather than hard-coding a vendor.

A request for a provider with no key gets a clear, actionable refusal rather
than a failed network call, which is the difference between "add a key in
Settings" and a stack trace.
"""

from __future__ import annotations

import base64
import uuid

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import jobs
from .media import ingest_path
from .paths import DATA_DIR
from .providers import PROVIDERS, base_for, key_for

router = APIRouter(prefix="/api/generate", tags=["generate"])

STAGING = DATA_DIR / "generated"

# Each entry says what the interface should offer. Sizes and durations are the
# provider's own, so the sheet cannot offer a shape the provider will refuse.
GENERATORS: dict[str, dict] = {
    "openai-image": {
        "label": "OpenAI images",
        "provider": "openai",
        "kind": "image",
        "sizes": ["1024x1024", "1536x1024", "1024x1536"],
        "options": {"quality": ["standard", "hd"], "count": {"min": 1, "max": 4, "default": 1}},
        "path": "/v1/images/generations",
    },
    "stability-image": {
        "label": "Stability images",
        "provider": "stability",
        "kind": "image",
        "sizes": ["1024x1024", "1344x768", "768x1344"],
        "options": {"steps": {"min": 10, "max": 50, "default": 30}, "count": {"min": 1, "max": 4, "default": 1}},
        "path": "/v2beta/stable-image/generate/core",
    },
    "replicate-video": {
        "label": "Replicate video",
        "provider": "replicate",
        "kind": "video",
        "sizes": ["1280x720", "720x1280", "1024x576"],
        "options": {"seconds": {"min": 2, "max": 10, "default": 5}, "fps": {"min": 8, "max": 30, "default": 24}},
        "path": "/v1/predictions",
    },
    "elevenlabs-sound": {
        "label": "ElevenLabs sound effects",
        "provider": "elevenlabs",
        "kind": "audio",
        "sizes": [],
        "options": {"seconds": {"min": 1, "max": 22, "default": 6}, "influence": {"min": 0, "max": 1, "default": 0.3}},
        "path": "/v1/sound-generation",
    },
}

# Providers the generators need that the registry did not already carry.
EXTRA_PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "env": "OPENAI_API_KEY",
        "base_env": "OPENAI_BASE",
        "base": "https://api.openai.com",
        "purpose": "generate",
    },
    "stability": {
        "label": "Stability AI",
        "env": "STABILITY_API_KEY",
        "base_env": "STABILITY_BASE",
        "base": "https://api.stability.ai",
        "purpose": "generate",
    },
    "replicate": {
        "label": "Replicate",
        "env": "REPLICATE_API_TOKEN",
        "base_env": "REPLICATE_BASE",
        "base": "https://api.replicate.com",
        "purpose": "generate",
    },
}
for _name, _entry in EXTRA_PROVIDERS.items():
    PROVIDERS.setdefault(_name, _entry)


class GenerateBody(BaseModel):
    generator: str
    prompt: str = Field(min_length=1, max_length=2000)
    negative: str = ""
    size: str | None = None
    seconds: float | None = None
    count: int = 1
    options: dict = {}


def catalogue() -> list[dict]:
    """What the interface may offer, with each entry's readiness."""
    out = []
    for key, entry in GENERATORS.items():
        provider = entry["provider"]
        out.append(
            {
                "id": key,
                "label": entry["label"],
                "kind": entry["kind"],
                "provider": provider,
                "providerLabel": PROVIDERS.get(provider, {}).get("label", provider),
                "sizes": entry["sizes"],
                "options": entry["options"],
                "ready": bool(key_for(provider)),
            }
        )
    return out


@router.get("")
def list_generators() -> dict:
    return {"generators": catalogue()}


def _payload(entry: dict, body: GenerateBody) -> tuple[dict, dict]:
    """The request body and headers for one provider, kept in one place."""
    key = key_for(entry["provider"])
    size = body.size or (entry["sizes"][0] if entry["sizes"] else None)
    if entry["provider"] == "openai":
        return (
            {"model": "gpt-image-1", "prompt": body.prompt, "size": size, "n": max(1, min(4, body.count))},
            {"Authorization": f"Bearer {key}"},
        )
    if entry["provider"] == "stability":
        width, _, height = (size or "1024x1024").partition("x")
        return (
            {
                "prompt": body.prompt,
                "negative_prompt": body.negative,
                "width": int(width),
                "height": int(height),
                "steps": int(body.options.get("steps", 30)),
            },
            {"Authorization": f"Bearer {key}", "Accept": "application/json"},
        )
    if entry["provider"] == "replicate":
        width, _, height = (size or "1280x720").partition("x")
        return (
            {
                "input": {
                    "prompt": body.prompt,
                    "negative_prompt": body.negative,
                    "width": int(width),
                    "height": int(height),
                    "num_frames": int(float(body.seconds or 5) * int(body.options.get("fps", 24))),
                }
            },
            {"Authorization": f"Bearer {key}"},
        )
    return (
        {"text": body.prompt, "duration_seconds": float(body.seconds or 6), "prompt_influence": float(body.options.get("influence", 0.3))},
        {"xi-api-key": key},
    )


def _extract(entry: dict, response: httpx.Response) -> list[bytes]:
    """Bytes of whatever the provider returned, however it chose to return it."""
    media_type = response.headers.get("content-type", "")
    if not media_type.startswith("application/json"):
        return [response.content]
    data = response.json()
    out: list[bytes] = []
    for item in data.get("data") or data.get("artifacts") or data.get("images") or []:
        if isinstance(item, dict):
            encoded = item.get("b64_json") or item.get("base64") or item.get("image")
            if encoded:
                out.append(base64.b64decode(encoded))
            elif item.get("url"):
                out.append(httpx.get(item["url"], timeout=120, follow_redirects=True).content)
    if not out and isinstance(data.get("output"), str):
        out.append(httpx.get(data["output"], timeout=300, follow_redirects=True).content)
    if not out:
        raise ValueError("The provider returned nothing that could be read as media")
    return out


@router.post("", status_code=202)
def generate(body: GenerateBody):
    entry = GENERATORS.get(body.generator)
    if not entry:
        raise HTTPException(404, "Unknown generator")
    if not key_for(entry["provider"]):
        label = PROVIDERS.get(entry["provider"], {}).get("label", entry["provider"])
        raise HTTPException(409, f"Add a {label} key in Settings before generating")

    def operation(job_id, report, cancelled):
        STAGING.mkdir(parents=True, exist_ok=True)
        payload, headers = _payload(entry, body)
        report(0.1)
        with httpx.Client(timeout=600, follow_redirects=True) as client:
            response = client.post(base_for(entry["provider"]).rstrip("/") + entry["path"], json=payload, headers=headers)
            if response.status_code >= 400:
                raise ValueError(f"{entry['label']} refused the request ({response.status_code}): {response.text[:300]}")
            report(0.6)
            blobs = _extract(entry, response)
        made = []
        for index, blob in enumerate(blobs):
            if cancelled():
                raise InterruptedError("Cancelled")
            suffix = {"image": ".png", "video": ".mp4", "audio": ".mp3"}[entry["kind"]]
            staged = STAGING / f"{uuid.uuid4().hex}{suffix}"
            staged.write_bytes(blob)
            try:
                made.append(
                    ingest_path(
                        staged,
                        f"{body.prompt[:48]} ({entry['label']})",
                        extra={"source": "generated", "generator": body.generator, "prompt": body.prompt},
                    )
                )
            finally:
                staged.unlink(missing_ok=True)
            report(0.6 + 0.4 * (index + 1) / len(blobs))
        return {"media": made, "kind": entry["kind"]}

    return jobs.submit("generate", operation)
