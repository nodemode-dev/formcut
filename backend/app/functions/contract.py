"""The Form function contract (hub plan 12.3): the manifest formcut declares, and the checks every call passes.

A function is `fn(inputs, params, out_dir) -> dict`. `inputs` maps each input name to a local file path; the return maps
each output name to a file inside `out_dir`. Params are checked against the manifest's own schema before anything runs,
and a failure is a FunctionError with a short message a person can act on.
"""

from __future__ import annotations

import re
from pathlib import Path

FORMAT = "form-functions"
FORMAT_VERSION = 1
APP = "formcut"

WHISPER_SIZES = ["tiny", "base", "small", "medium", "large"]
EXPORT_FORMATS = ["mp4", "webm", "gif"]
EXPORT_QUALITIES = ["high", "medium", "low"]

FUNCTIONS = [
    {
        "id": "transcribe",
        "title": "Transcribe",
        "description": (
            "Speech to text with formcut's own Whisper (ONNX Runtime, CPU): segments with start, end, text and word"
            " times as JSON, and the same speech as SRT captions."
        ),
        "entry": "app.functions:transcribe",
        "inputs": [{"name": "media", "kind": "media", "required": True, "many": False}],
        "outputs": [
            {"name": "transcript", "kind": "transcript", "ext": "json"},
            {"name": "subtitles", "kind": "transcript", "ext": "srt"},
        ],
        "params": {
            "type": "object",
            "properties": {
                "model": {"type": "string", "enum": WHISPER_SIZES, "default": "tiny"},
                "language": {"type": "string", "pattern": "^(auto|[a-z]{2,3})$", "default": "en"},
            },
            "required": [],
            "additionalProperties": False,
        },
        "runs": ["job"],
        "cost": "cpu",
        "timeout_s": 3600,
    },
    {
        "id": "render_project",
        "title": "Render project",
        "description": (
            "Renders a formcut project (.fc package, or .fmc file with its media beside it) through the engine's own"
            " export path, the renderer the preview uses."
        ),
        "entry": "app.functions:render_project",
        "inputs": [{"name": "project", "kind": "project.formcut", "required": True, "many": False}],
        "outputs": [
            {
                "name": "video",
                "kind": "video",
                "ext": "mp4",
                "by_param": {"format": {fmt: {"kind": "video", "ext": fmt} for fmt in EXPORT_FORMATS}},
            }
        ],
        "params": {
            "type": "object",
            "properties": {
                "format": {"type": "string", "enum": EXPORT_FORMATS, "default": "mp4"},
                "quality": {"type": "string", "enum": EXPORT_QUALITIES, "default": "high"},
            },
            "required": [],
            "additionalProperties": False,
        },
        "runs": ["job"],
        "cost": "cpu",
        "timeout_s": 3600,
    },
]


class FunctionError(Exception):
    """A function refused or failed; the message is short and says what to change."""


def manifest(app_version: str) -> dict:
    return {"format": FORMAT, "format_version": FORMAT_VERSION, "app": APP, "app_version": app_version, "functions": FUNCTIONS}


def spec(function_id: str) -> dict:
    found = next((f for f in FUNCTIONS if f["id"] == function_id), None)
    if found is None:
        raise FunctionError(f"no function named {function_id!r}; formcut has {', '.join(f['id'] for f in FUNCTIONS)}")
    return found


def checked_params(function_id: str, params: dict | None) -> dict:
    """The params with their defaults filled in, refused unless they match the manifest's schema."""
    schema = spec(function_id)["params"]
    given = {} if params is None else params
    if not isinstance(given, dict):
        raise FunctionError("params must be an object")
    known = schema["properties"]
    unknown = sorted(set(given) - set(known))
    if unknown and schema.get("additionalProperties") is False:
        raise FunctionError(f"unknown param {unknown[0]!r}; {function_id} takes {', '.join(known)}")
    for name in schema.get("required", []):
        if name not in given:
            raise FunctionError(f"param {name!r} is required")
    result = {}
    for name, rule in known.items():
        value = given.get(name, rule.get("default"))
        if value is None:
            continue
        if rule.get("type") == "string" and not isinstance(value, str):
            raise FunctionError(f"param {name!r} must be a string")
        if "enum" in rule and value not in rule["enum"]:
            raise FunctionError(f"param {name!r} is {value!r}; expected one of {', '.join(rule['enum'])}")
        if "pattern" in rule and not re.fullmatch(rule["pattern"], value):
            raise FunctionError(f"param {name!r} is {value!r}; expected {rule['pattern']}")
        result[name] = value
    return result


def input_file(inputs: dict | None, name: str) -> Path:
    """The local file given for a required single input."""
    value = (inputs or {}).get(name)
    if not value:
        raise FunctionError(f"input {name!r} is required")
    if not isinstance(value, str):
        raise FunctionError(f"input {name!r} must be one file path")
    path = Path(value).expanduser()
    if not path.is_file():
        raise FunctionError(f"input {name!r}: no file at {path}")
    return path.resolve()


# Every field by which the renderer looks an item up in the engine's library: media files (clips, device screens, an
# image background), LUTs and shaders (clips) and fonts (text styles). None of them has a built-in item by id.
LIBRARY_KEYS = {"mediaId": "media", "lutId": "LUT", "shaderId": "shader", "fontId": "font"}


def library_references(value) -> list[tuple[str, str]]:
    """(key, id) for every library reference anywhere in a document, at any depth."""
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key in LIBRARY_KEYS and isinstance(child, str) and child:
                found.append((key, child))
            else:
                found.extend(library_references(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(library_references(child))
    return found


def output_dir(out_dir: str) -> Path:
    folder = Path(out_dir).expanduser()
    folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()
