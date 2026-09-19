"""Effect packages defined as data (P3).

A package is a folder under `effects/` in the data directory containing a
manifest and one backend: a filter-chain template with parameter slots (video
or audio) or a WGSL shader (video). Packages load at start and after Import
package; a package that fails to load is collected with its reason and listed
in Settings rather than stopping the engine.

The filter allowlist is the security boundary: a chain template may only name
filters the engine already uses, so a package cannot smuggle arbitrary ffmpeg
(a file writer, a device input) into the render path.
"""
from __future__ import annotations

import json
import re
import threading

from .paths import DATA_DIR

PACKAGES = DATA_DIR / "effects"

# Filters a package may name. Everything the built-in chains use, and nothing
# that reads or writes outside the stream it was handed.
ALLOWED_FILTERS = {
    "acompressor", "adeclick", "adelay", "aecho", "aemphasis", "afftdn", "aformat", "agate",
    "alimiter", "allpass", "aphaser", "areverse", "asetrate", "atempo", "atrim", "bandpass",
    "bandreject", "bass", "chorus", "compand", "crystalizer", "deesser", "dynaudnorm",
    "equalizer", "extrastereo", "flanger", "highpass", "loudnorm", "lowpass", "rubberband",
    "speechnorm", "stereotools", "stereowiden", "treble", "tremolo", "vibrato", "volume",
}

PARAM_NAME = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
SLOT = re.compile(r"\{([a-z][a-z0-9_]{0,31})\}")

_lock = threading.RLock()
_loaded: dict[str, dict] = {}
_failures: list[dict] = []


def _fail(name: str, reason: str) -> None:
    _failures.append({"package": name, "reason": reason})


def _check_manifest(manifest: dict) -> str | None:
    """A reason the manifest is unusable, or None."""
    if not isinstance(manifest, dict):
        return "the manifest is not an object"
    for field in ("id", "name", "kind"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            return f"the manifest needs a {field}"
    if manifest["kind"] not in ("video", "audio"):
        return "kind must be video or audio"
    if not re.match(r"^[a-z0-9][a-z0-9-]{1,63}$", manifest["id"]):
        return "the id must be lowercase letters, digits and hyphens"
    declarations = manifest.get("parameters") or {}
    if not isinstance(declarations, dict) or len(declarations) > 16:
        return "parameters must be an object of at most sixteen entries"
    for name, spec in declarations.items():
        if not PARAM_NAME.match(name):
            return f"parameter name {name!r} is not usable"
        if not isinstance(spec, dict):
            return f"parameter {name} needs a declaration"
        for field in ("min", "max", "default"):
            if not isinstance(spec.get(field), (int, float)):
                return f"parameter {name} needs a numeric {field}"
        if not spec["min"] <= spec["default"] <= spec["max"]:
            return f"parameter {name} has a default outside its range"
    return None


def _check_chain(template: str, declarations: dict) -> str | None:
    """A reason a filter-chain template is unusable, or None."""
    if not isinstance(template, str) or not template.strip():
        return "the chain is empty"
    if len(template) > 2000:
        return "the chain is too long"
    for slot in SLOT.findall(template):
        if slot not in declarations:
            return f"the chain uses {{{slot}}} but declares no such parameter"
    # A chain is filters separated by commas; each filter is name=args or name.
    for step in template.split(","):
        head = step.strip().split("=", 1)[0].strip()
        if head not in ALLOWED_FILTERS:
            return f"filter {head!r} is not in the engine allowlist"
    return None


def load_package(folder) -> dict:
    """Load one package folder, raising ValueError with a readable reason."""
    manifest_path = folder / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("no manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"the manifest is not valid json ({exc})") from exc
    reason = _check_manifest(manifest)
    if reason:
        raise ValueError(reason)
    declarations = manifest.get("parameters") or {}
    chain_path = folder / "chain.txt"
    shader_path = folder / "shader.wgsl"
    if chain_path.is_file():
        template = chain_path.read_text(encoding="utf-8").strip()
        reason = _check_chain(template, declarations)
        if reason:
            raise ValueError(reason)
        backend = {"type": "chain", "template": template}
    elif shader_path.is_file():
        source = shader_path.read_text(encoding="utf-8")
        if len(source) > 200_000:
            raise ValueError("the shader is too long")
        if manifest["kind"] != "video":
            raise ValueError("a shader package must be kind video")
        backend = {"type": "shader", "source": source}
    else:
        raise ValueError("no chain.txt or shader.wgsl")
    return {
        "id": manifest["id"],
        "name": manifest["name"],
        "kind": manifest["kind"],
        "category": manifest.get("category", "Packages"),
        "parameters": {name: spec["default"] for name, spec in declarations.items()},
        "declarations": declarations,
        "backend": backend,
        "folder": str(folder),
        "package": True,
    }


def reload() -> dict:
    """Load every package folder; failures are collected, never raised."""
    with _lock:
        _loaded.clear()
        _failures.clear()
        if PACKAGES.is_dir():
            for folder in sorted(p for p in PACKAGES.iterdir() if p.is_dir()):
                try:
                    entry = load_package(folder)
                except ValueError as exc:
                    _fail(folder.name, str(exc))
                    continue
                except Exception as exc:  # a package must never stop the start
                    _fail(folder.name, f"unreadable ({exc})")
                    continue
                if entry["id"] in _loaded:
                    _fail(folder.name, f"id {entry['id']} is already used")
                    continue
                _loaded[entry["id"]] = entry
        return {"loaded": list(_loaded), "failures": list(_failures)}


def entries(kind: str | None = None) -> list[dict]:
    with _lock:
        return [dict(entry) for entry in _loaded.values() if kind is None or entry["kind"] == kind]


def failures() -> list[dict]:
    with _lock:
        return list(_failures)


def find(effect_id: str) -> dict | None:
    with _lock:
        entry = _loaded.get(effect_id)
        return dict(entry) if entry else None


def chain_for(effect_id: str, params: dict | None) -> str | None:
    """A package's filter chain with its parameters filled in and clamped."""
    entry = find(effect_id)
    if not entry or entry["backend"]["type"] != "chain":
        return None
    values = {}
    for name, spec in entry["declarations"].items():
        raw = (params or {}).get(name, spec["default"])
        try:
            number = float(raw)
        except (TypeError, ValueError):
            number = float(spec["default"])
        values[name] = max(float(spec["min"]), min(float(spec["max"]), number))
    return SLOT.sub(lambda m: f"{values[m.group(1)]:g}", entry["backend"]["template"])
