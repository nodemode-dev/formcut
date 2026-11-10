"""The Form functions from a shell, for people and tests (the hub's runner imports the entries directly).

    python -m app.functions run transcribe --inputs '{"media": "talk.mp4"}' --params '{"model": "base"}' --out out/
    python -m app.functions manifest [--write]

`run` prints the result as one JSON line and exits 0, or prints the error to stderr and exits 1. `manifest` prints
the manifest, or with --write writes form-functions.json at the repository root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import FunctionError, manifest, render_project, transcribe
from .isolation import FAILED

ENTRIES = {"transcribe": transcribe, "render_project": render_project}
ROOT_MANIFEST = Path(__file__).resolve().parents[3] / "form-functions.json"


def manifest_text() -> str:
    from ..main import APP_VERSION

    return json.dumps(manifest(APP_VERSION), indent=2) + "\n"


def _object(text: str, flag: str) -> dict:
    try:
        value = json.loads(text)
    except ValueError as exc:
        raise FunctionError(f"{flag} is not JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise FunctionError(f"{flag} must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.functions", description="formcut's Form functions")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, text in (("run", "run one function"), ("_here", "internal: run one function in this process")):
        run = commands.add_parser(name, help=text)
        run.add_argument("function", choices=sorted(ENTRIES))
        run.add_argument("--inputs", required=True, help='JSON object, input name to file path, e.g. {"media": "a.mp4"}')
        run.add_argument("--params", default="{}", help="JSON object of params")
        run.add_argument("--out", required=True, help="folder the outputs are written to")
    listing = commands.add_parser("manifest", help="print the manifest")
    listing.add_argument("--write", action="store_true", help="write form-functions.json at the repository root")
    args = parser.parse_args(argv)
    if args.command == "manifest":
        text = manifest_text()
        if args.write:
            ROOT_MANIFEST.write_text(text, encoding="utf-8")
        sys.stdout.write(text if not args.write else f"{ROOT_MANIFEST}\n")
        return 0
    if args.command == "_here":
        return _here(args)
    try:
        result = ENTRIES[args.function](_object(args.inputs, "--inputs"), _object(args.params, "--params"), args.out)
    except FunctionError as exc:
        sys.stderr.write(f"{args.function}: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


def _here(args) -> int:
    """The child side of isolation.py: the work in this process, a FunctionError reported as {"error": ...}."""
    from ..tools import prefer_bundled
    from .rendering import render_project_here
    from .transcription import transcribe_here

    prefer_bundled()  # formcut's own ffmpeg first, as the engine puts it at start (FORMCUT_FFMPEG_DIR, then its folders)

    here = {"transcribe": transcribe_here, "render_project": render_project_here}[args.function]
    try:
        result = here(_object(args.inputs, "--inputs"), _object(args.params, "--params"), args.out)
    except FunctionError as exc:
        sys.stdout.write(json.dumps({"error": str(exc)}) + "\n")
        return FAILED
    sys.stdout.write(json.dumps(result) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
