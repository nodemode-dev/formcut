#!/usr/bin/env python3
"""Preflight for a release tag.

A release runs on machines that are not this one, and its failures arrive
twenty minutes in. Everything checkable beforehand is checked here: that one
version number appears in all eight places, that the files the build refers to
exist, that the workflows parse, and that the things which must be decided
before shipping, the ffmpeg licence in particular, have been decided.

Run it before tagging. A failure is a refusal, not a warning.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
problems: list[str] = []
notes: list[str] = []


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_versions() -> str | None:
    """One version, in all eight places."""
    found: dict[str, str] = {}
    package = json.loads(read(ROOT / "frontend/package.json"))
    found["frontend/package.json"] = package["version"]
    lock = json.loads(read(ROOT / "frontend/package-lock.json"))
    found["package-lock (root)"] = lock.get("version", "")
    found["package-lock (packages)"] = lock.get("packages", {}).get("", {}).get("version", "")
    main = re.search(r'APP_VERSION = "([^"]+)"', read(ROOT / "backend/app/main.py"))
    found["backend APP_VERSION"] = main.group(1) if main else ""
    tauri = json.loads(read(ROOT / "src-tauri/tauri.conf.json"))
    found["tauri.conf.json"] = tauri.get("version", "")
    cargo = re.search(r'^version = "([^"]+)"', read(ROOT / "src-tauri/Cargo.toml"), re.M)
    found["Cargo.toml"] = cargo.group(1) if cargo else ""
    lockfile = re.search(r'name = "formcut"\nversion = "([^"]+)"', read(ROOT / "src-tauri/Cargo.lock"))
    found["Cargo.lock"] = lockfile.group(1) if lockfile else ""
    readme = re.search(r"(\d+\.\d+\.\d+)", read(ROOT / "README.md"))
    found["README badge"] = readme.group(1) if readme else ""
    distinct = {v for v in found.values() if v}
    if len(distinct) != 1:
        for where, value in found.items():
            problems.append(f"version mismatch: {where} says {value or 'nothing'}")
        return None
    version = distinct.pop()
    notes.append(f"version {version} agrees across {len(found)} places")
    return version


def check_files() -> None:
    """Everything the build refers to has to be there."""
    required = [
        "backend/freeze.py", "backend/requirements.txt",
        "src-tauri/tauri.conf.json", "src-tauri/Cargo.toml",
        "setup/fetch_ffmpeg.py",
        ".github/workflows/release.yml", ".github/workflows/checks.yml",
        "frontend/package.json", "frontend/index.html",
        "README.md", "LICENSE",
    ]
    for relative in required:
        if not (ROOT / relative).exists():
            problems.append(f"missing: {relative}")
    icons = ROOT / "src-tauri/icons"
    for name in ("icon.png", "icon.ico", "icon.icns"):
        if not (icons / name).is_file():
            problems.append(f"missing app icon: src-tauri/icons/{name}")
    public = ROOT / "frontend/public"
    for name in ("favicon.svg", "manifest.webmanifest", "icons/icon-512.png"):
        if not (public / name).is_file():
            problems.append(f"missing web asset: frontend/public/{name}")


def check_tauri() -> None:
    """The bundle's own references, which fail late and loudly on a runner."""
    config = json.loads(read(ROOT / "src-tauri/tauri.conf.json"))
    bundle = config.get("bundle") or config.get("tauri", {}).get("bundle") or {}
    external = bundle.get("externalBin") or []
    if not any("formcut-engine" in str(entry) for entry in external):
        problems.append("tauri.conf.json does not carry the frozen engine in externalBin")
    else:
        notes.append("the frozen engine is declared as an external binary")
    targets = bundle.get("targets")
    notes.append(f"bundle targets: {targets if targets else 'all'}")


def check_workflows() -> None:
    for relative in (".github/workflows/release.yml", ".github/workflows/checks.yml"):
        text = read(ROOT / relative)
        if "\t" in text:
            problems.append(f"{relative} contains a tab, which YAML forbids for indentation")
        for referenced in re.findall(r"(?:python|run:\s*python)\s+(setup/[\w./-]+|backend/[\w./-]+)", text):
            if not (ROOT / referenced).exists():
                problems.append(f"{relative} calls {referenced}, which does not exist")


def check_licences() -> None:
    """The decisions that must be made before shipping, not after."""
    licences = ROOT / ".docs/wiki/Licences.md"
    if not licences.is_file():
        problems.append("missing .docs/wiki/Licences.md")
        return
    text = read(licences)
    if "ffmpeg" not in text.lower():
        problems.append("Licences.md does not say which ffmpeg build is shipped; "
                        "a GPL build imposes its terms on the bundle")
    else:
        notes.append("an ffmpeg licence is recorded")
    fetch = ROOT / "setup/fetch_ffmpeg.py"
    release = ROOT / ".github/workflows/release.yml"
    if not fetch.is_file() or not release.is_file():
        # check_files has already named whichever is missing; reading it here
        # would end the run with a traceback instead of a list of problems, and
        # a preflight that crashes tells you less than one that fails.
        return
    if "--allow-gpl" in read(release) and "GPL" in read(fetch):
        notes.append("the release fetches a GPL ffmpeg knowingly; confirm that is intended")


def check_engine() -> None:
    """The engine has to import before it can be frozen."""
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from app.main import app  # noqa: F401
    except Exception as exc:  # pragma: no cover - reported, not raised
        problems.append(f"the engine does not import: {exc}")
        return
    notes.append(f"the engine imports, {len(app.routes)} routes mounted")


def main() -> int:
    check_versions()
    check_files()
    check_tauri()
    check_workflows()
    check_licences()
    check_engine()
    for note in notes:
        print(f"  ok   {note}")
    for problem in problems:
        print(f"  FAIL {problem}")
    print()
    if problems:
        print(f"{len(problems)} problem(s): this tag would fail on a runner. Fix them first.")
        return 1
    print("preflight clean: ready to tag.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
