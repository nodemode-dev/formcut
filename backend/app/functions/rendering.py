"""render_project: a formcut project file to a video, through the engine's own export path.

The same render as POST /api/render/export: render_document.validate_document, then render_api.export_media, the
renderer the preview draws with, run in this process with no engine server. The project's media must come with it:

- a .fc package carries its media; project_packages.unpack_document ingests them as opening a package does, and any
  clip naming media the package does not hold is refused.
- a .fmc names its media in a table, each also relative to the .fmc's folder; only that relative path is read, it
  must stay inside the folder, and each file is linked into the library (linking.link_path) under a new id.

Nothing is saved to the project store, and the exported file is moved into out_dir.
"""

from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from fastapi import HTTPException

from .. import encoders, linking, media, openh264, project_files, project_packages, render_api
from ..render_document import validate_document
from .contract import FunctionError, checked_params, input_file, output_dir


def render_project(inputs: dict, params: dict, out_dir: str) -> dict:
    options = checked_params("render_project", params)
    source = input_file(inputs, "project")
    folder = output_dir(out_dir)
    document, brought = _document(source)
    _require_media(document, brought)
    try:
        project = validate_document({k: v for k, v in document.items() if k != "revision"})
    except (TypeError, ValueError, KeyError) as exc:
        raise FunctionError(f"the project cannot be rendered: {exc}") from exc
    fmt = options["format"]
    _require_encoder(fmt)
    job_id = uuid.uuid4().hex
    try:
        result = render_api.export_media(project, job_id, lambda _f: None, lambda: False, fmt, options["quality"])
    except (ValueError, RuntimeError, OSError) as exc:
        raise FunctionError(f"the render failed: {str(exc).strip()[-500:]}") from exc
    rendered = Path(result["file"])
    if rendered.suffix.lower() != f".{fmt}":
        rendered.unlink(missing_ok=True)
        raise FunctionError(f"this engine could only write {rendered.suffix or 'nothing'}, not .{fmt}")
    target = folder / f"video.{fmt}"
    shutil.move(str(rendered), target)
    return {"video": str(target)}


def _document(source: Path) -> tuple[dict, set[str]]:
    """The project document with its media ids rewritten to the files that came with it, and those ids."""
    suffix = source.suffix.lower()
    if suffix == ".fc":
        try:
            document, _manifest, replacements, _index = project_packages.unpack_document(source)
        except (ValueError, KeyError, TypeError) as exc:
            raise FunctionError(f"{source.name}: {exc}") from exc
        except HTTPException as exc:
            raise FunctionError(f"{source.name}: {exc.detail}") from exc
        return document, set(replacements.values())
    if suffix == project_files.SUFFIX:
        return _from_project_file(source)
    raise FunctionError(f"{source.name} is not a formcut project: give a .fc package or a .fmc file")


def _from_project_file(source: Path) -> tuple[dict, set[str]]:
    try:
        saved = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise FunctionError(f"{source.name} could not be read as a formcut project file") from exc
    if not isinstance(saved, dict) or saved.get("format") != project_files.FORMAT or not isinstance(saved.get("project"), dict):
        raise FunctionError(f"{source.name} is not a formcut project file")
    if int(saved.get("version", 0)) > project_files.VERSION:
        raise FunctionError(f"{source.name} was written by a newer formcut ({saved.get('app')})")
    document = saved["project"]
    table = saved.get("media") if isinstance(saved.get("media"), dict) else {}
    home = source.parent
    replacements = {}
    for media_id in sorted({media_id for _clip, media_id in project_packages._media_uses(document)}):
        found = _beside(home, table.get(media_id) or {}, media_id)
        try:
            item = linking.link_path(found, name=(table.get(media_id) or {}).get("name"), media_id=uuid.uuid4().hex)
        except HTTPException as exc:
            raise FunctionError(f"{found.name}: {exc.detail}") from exc
        replacements[media_id] = item["id"]
    project_packages.rewrite_references(document, replacements)
    return document, set(replacements.values())


def _beside(home: Path, entry: dict, media_id: str) -> Path:
    """The media file at the path the table gives relative to the .fmc, refused unless it is inside the .fmc's folder."""
    name = entry.get("name") or media_id
    relative = entry.get("relative")
    if not isinstance(relative, str) or not relative:
        raise FunctionError(f"media {name!r} has no path relative to the project file; collect the project first")
    found = (home / relative).resolve()
    if not found.is_relative_to(home.resolve()):
        raise FunctionError(f"media {name!r} is outside the project's folder ({relative}); collect the project or send a .fc")
    if not found.is_file():
        raise FunctionError(f"media {name!r} is missing: no file at {relative} beside the project file")
    return found


def _require_media(document: dict, brought: set[str]) -> None:
    """Every clip's media came with the project: never a library item that merely shares its id."""
    for clip, media_id in project_packages._media_uses(document):
        if media_id not in brought or media.media_path(media_id) is None:
            label = clip.get("label") or clip.get("id")
            raise FunctionError(f"clip {label!r} uses media that did not come with the project")


def _require_encoder(fmt: str) -> None:
    """An mp4 needs an H.264 encoder here, or OpenH264 already installed: this function never downloads one."""
    if fmt != "mp4" or encoders.choose("h264") or openh264.library(download=False):
        return
    raise FunctionError("this FFmpeg has no H.264 encoder and OpenH264 is not installed; render webm, or add an encoder")
