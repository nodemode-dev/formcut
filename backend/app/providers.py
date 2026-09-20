"""Provider keys, their state, and a real connection test for each.

Keys reach the engine three ways and are read in this order: a key stored here
by the interface, then the environment, then nothing. Storing them in the engine
rather than the browser means a key never sits in localStorage, never travels in
a project file, and survives a browser cache clear; it also means the interface
can be told a key exists without being told what it is.

Nothing here ever returns a key. State carries only whether one is configured,
where it came from, and the last four characters, which is enough for a person
to tell which key is loaded.
"""

import contextlib
import json
import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .paths import DATA_DIR

router = APIRouter(prefix="/api/providers", tags=["providers"])

STORE = DATA_DIR / "providers.json"

PROVIDERS = {
    "pexels": {
        "label": "Pexels",
        "env": "PEXELS_API_KEY",
        "base_env": "PEXELS_BASE",
        "base": "https://api.pexels.com",
        "purpose": "stock",
    },
    "elevenlabs": {
        "label": "ElevenLabs",
        "env": "ELEVENLABS_API_KEY",
        "base_env": "ELEVENLABS_BASE",
        "base": "https://api.elevenlabs.io",
        "purpose": "speech",
    },
}


class KeyInput(BaseModel):
    key: str


def _read() -> dict[str, str]:
    try:
        return json.loads(STORE.read_text())
    except (OSError, ValueError):
        return {}


def _write(data: dict[str, str]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data))
    # The file holds credentials, so it is readable by its owner only. On
    # Windows this is a no-op and the platform ACL applies instead.
    with contextlib.suppress(OSError):
        STORE.chmod(0o600)


def key_for(name: str) -> str:
    """The key in force for a provider: stored first, then the environment."""
    stored = _read().get(name, "").strip()
    if stored:
        return stored
    spec = PROVIDERS.get(name)
    return os.environ.get(spec["env"], "").strip() if spec else ""


def base_for(name: str) -> str:
    """The endpoint in force, overridable for a proxy, mirror or local stub."""
    spec = PROVIDERS[name]
    return os.environ.get(spec["base_env"], "").strip().rstrip("/") or spec["base"]


def _state(name: str) -> dict:
    spec = PROVIDERS[name]
    stored = _read().get(name, "").strip()
    env = os.environ.get(spec["env"], "").strip()
    key = stored or env
    return {
        "id": name,
        "label": spec["label"],
        "purpose": spec["purpose"],
        "configured": bool(key),
        "source": "stored" if stored else ("environment" if env else "none"),
        "hint": key[-4:] if len(key) >= 4 else "",
        "base": base_for(name),
        "envName": spec["env"],
    }


@router.get("")
def list_providers() -> list[dict]:
    return [_state(name) for name in PROVIDERS]


@router.post("/{name}/key")
def set_key(name: str, body: KeyInput) -> dict:
    if name not in PROVIDERS:
        raise HTTPException(status_code=404, detail="unknown provider")
    key = body.key.strip()
    if not key:
        raise HTTPException(status_code=422, detail="the key is empty")
    data = _read()
    data[name] = key
    _write(data)
    return _state(name)


@router.delete("/{name}/key")
def clear_key(name: str) -> dict:
    if name not in PROVIDERS:
        raise HTTPException(status_code=404, detail="unknown provider")
    data = _read()
    if data.pop(name, None) is not None:
        _write(data)
    return _state(name)


@router.post("/{name}/test")
def test_provider(name: str) -> dict:
    """Ask the provider something cheap and report exactly what came back."""
    if name not in PROVIDERS:
        raise HTTPException(status_code=404, detail="unknown provider")
    key = key_for(name)
    if not key:
        return {**_state(name), "ok": False, "detail": f"No key. Set one here or as {PROVIDERS[name]['env']} in .env."}
    base = base_for(name)
    try:
        if name == "pexels":
            response = httpx.get(f"{base}/v1/search", params={"query": "test", "per_page": 1},
                                 headers={"Authorization": key}, timeout=20.0)
            detail = f"{len(response.json().get('photos', []))} result returned" if response.status_code == 200 else ""
        else:
            response = httpx.get(f"{base}/v1/voices", headers={"xi-api-key": key}, timeout=20.0)
            detail = f"{len(response.json().get('voices', []))} voices available" if response.status_code == 200 else ""
    except (httpx.HTTPError, ValueError) as error:
        return {**_state(name), "ok": False, "detail": f"Could not reach {base}: {error.__class__.__name__}"}
    if response.status_code == 200:
        return {**_state(name), "ok": True, "detail": detail}
    reason = "the key was rejected" if response.status_code in (401, 403) else f"HTTP {response.status_code}"
    return {**_state(name), "ok": False, "detail": f"{PROVIDERS[name]['label']} answered: {reason}"}
