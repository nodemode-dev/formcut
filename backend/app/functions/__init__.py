"""formcut's Form functions: typed files in, typed files out, no window and no engine server (hub plan section 12).

`form-functions.json` at the repository root declares them (written from contract.FUNCTIONS by
`python -m app.functions manifest --write`); each entry is a callable here, `fn(inputs, params, out_dir) -> dict`.

Each call checks its params and inputs, then runs in a child process with a fresh, empty data folder of its own
(isolation.py), so it can neither read from nor add to a person's library, whatever FORMCUT_DATA_DIR says. The models
folder is shared: from a checkout `models/` beside `backend/` (or FORMCUT_MODELS_DIR), so a Whisper model is fetched
once.
"""

from __future__ import annotations

from .contract import FunctionError, manifest
from .isolation import run_isolated


def transcribe(inputs: dict, params: dict, out_dir: str) -> dict:
    """Speech in a media file to transcript.json and subtitles.srt (transcription.py)."""
    return run_isolated("transcribe", inputs, params, out_dir)


def render_project(inputs: dict, params: dict, out_dir: str) -> dict:
    """A .fc or .fmc project rendered to video.<format> (rendering.py)."""
    return run_isolated("render_project", inputs, params, out_dir)


__all__ = ["FunctionError", "manifest", "render_project", "transcribe"]
