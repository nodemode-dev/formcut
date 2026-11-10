"""formcut's Form functions: typed files in, typed files out, no window and no engine server (hub plan section 12).

`form-functions.json` at the repository root declares them (written from contract.FUNCTIONS by
`python -m app.functions manifest --write`); each entry is a callable here, `fn(inputs, params, out_dir) -> dict`.

The engine keeps a library, a project store and its renders in its data folder. Imported before the rest of the engine,
with no FORMCUT_DATA_DIR set, this package points the data folder at a private temporary one (removed at exit), so a
function never adds media or renders to a person's own library. The models folder is not moved: from a checkout it
is `models/` beside `backend/` (or FORMCUT_MODELS_DIR), so a downloaded Whisper model is kept between runs.
"""

from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile

if "FORMCUT_DATA_DIR" not in os.environ and "app.paths" not in sys.modules:
    _PRIVATE = tempfile.mkdtemp(prefix="formcut-functions-")
    os.environ["FORMCUT_DATA_DIR"] = _PRIVATE
    os.environ.setdefault("FORMCUT_NO_WARM", "1")
    atexit.register(shutil.rmtree, _PRIVATE, ignore_errors=True)

from .contract import FunctionError, manifest
from .rendering import render_project
from .transcription import transcribe

__all__ = ["FunctionError", "manifest", "render_project", "transcribe"]
