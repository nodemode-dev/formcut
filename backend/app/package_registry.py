"""The community package registry.

A registry is one JSON index (format formcut-effects-registry) hosted
anywhere; formcut's own lives in the repository under .docs/registry and is
read from its raw GitHub URL by default, and FORMCUT_PACKAGE_REGISTRY or the
url query names another. Each entry points at a zip of a package folder. An
install downloads it (4 MB ceiling, the installer's own), checks the entry's
sha256 when the index gives one, and hands the bytes to effect_packages.install,
so a registry package gets exactly the checks a dropped package gets: the
manifest gate, the filter allowlist, the shader trial.
"""

import hashlib
import json
import os

import httpx

from .effect_packages import MAX_UPLOAD, install

DEFAULT_INDEX = "https://raw.githubusercontent.com/nodemode-dev/formcut/main/.docs/registry/effects-registry.json"
FORMAT = "formcut-effects-registry"
FIELDS = ("id", "name", "kind", "author", "description", "url", "sha256")


def index_url(url: str | None = None) -> str:
    return url or os.environ.get("FORMCUT_PACKAGE_REGISTRY") or DEFAULT_INDEX


def _get(url: str, limit: int) -> bytes:
    if not url.startswith(("https://", "http://")):
        raise ValueError("the registry URL must be http or https")
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=30) as response:
            if response.status_code != 200:
                raise ValueError(f"{url} answered {response.status_code}")
            chunks = []
            total = 0
            for chunk in response.iter_bytes():
                total += len(chunk)
                if total > limit:
                    raise ValueError(f"{url} is larger than {limit // 1_000_000} MB")
                chunks.append(chunk)
            return b"".join(chunks)
    except httpx.HTTPError as exc:
        raise ValueError(f"could not reach {url}: {exc.__class__.__name__}") from exc


def fetch_index(url: str | None = None) -> dict:
    """The index, validated to its listed fields, with the URL it came from."""
    source = index_url(url)
    raw = _get(source, 2_000_000)
    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("the registry index is not JSON") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError("that URL is not a formcut package registry")
    packages = []
    for entry in data.get("packages") or []:
        if not isinstance(entry, dict) or not entry.get("id") or not entry.get("url"):
            continue
        packages.append({field: entry.get(field) for field in FIELDS})
    return {
        "url": source,
        "name": str(data.get("name") or "Package registry"),
        "description": str(data.get("description") or ""),
        "packages": packages[:200],
    }


def install_from_url(url: str, sha256: str | None = None) -> dict:
    """Download one package zip, verify it when a hash is given, install it."""
    data = _get(url, MAX_UPLOAD)
    if sha256:
        digest = hashlib.sha256(data).hexdigest()
        if digest != sha256.lower():
            raise ValueError("the downloaded package does not match the registry's hash; nothing was installed")
    name = url.rsplit("/", 1)[-1] or "package.zip"
    return install(data, name)
