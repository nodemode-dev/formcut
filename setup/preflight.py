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
    cargo = re.search(r'^version = "([^"]+)"', read(ROOT / "src-tauri/Cargo.toml"), re.MULTILINE)
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
        "backend/freeze.py",
        "backend/requirements.txt",
        "src-tauri/tauri.conf.json",
        "src-tauri/entitlements.plist",
        "src-tauri/Cargo.toml",
        "src-tauri/binaries/ffmpeg-licence.json",
        "src-tauri/ffmpeg/README.md",
        "setup/build_release",
        "setup/build_phone",
        "setup/release_assets",
        ".github/workflows/checks.yml",
        "frontend/package.json",
        "frontend/index.html",
        "README.md",
        "LICENSE",
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
    notes.append(f"bundle targets: {targets or 'all'}")


def check_workflows() -> None:
    checks = ROOT / ".github/workflows/checks.yml"
    if "\t" in read(checks):
        problems.append(".github/workflows/checks.yml contains a tab, which YAML forbids for indentation")
    # The build lives in setup/build_release, run by nodemode-ai/formcompiler.
    relative = "setup/build_release"
    script = ROOT / relative
    if script.is_file():
        for referenced in re.findall(r"(?:python|run:\s*python)\s+(setup/[\w./-]+|backend/[\w./-]+)", read(script)):
            if not (ROOT / referenced).exists():
                problems.append(f"{relative} calls {referenced}, which does not exist")


def check_licences() -> None:
    """The decisions that must be made before shipping, not after."""
    licences = ROOT / ".docs/wiki/Licences.md"
    if not licences.is_file():
        problems.append("missing .docs/wiki/Licences.md")
        return
    text = read(licences)
    # A workflow that does not parse is not a failing check, it is no check at
    # all: GitHub refuses the file and reports a failure with no duration and no
    # logs. That is how a release went out with the checks silently not running,
    # so the files are parsed here before anything can be tagged.
    try:
        import yaml
    except ImportError:
        problems.append("pyyaml is not installed, so the workflows cannot be checked; pip install pyyaml")
    else:
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                problems.append(f"{path.name} is not valid yaml: {str(exc)[:90]}")
                continue
            jobs = (loaded or {}).get("jobs") or {}
            if not jobs:
                problems.append(f"{path.name} declares no jobs")
                continue
            for name, job in jobs.items():
                for step in job.get("steps") or []:
                    if not (step.get("run") or step.get("uses")):
                        problems.append(f"{path.name}: a step in {name} does nothing")
            notes.append(f"{path.name} parses, {len(jobs)} job(s)")
        # The suite has to be wired in, not merely present in the repository.
        checks = ROOT / ".github/workflows/checks.yml"
        if checks.is_file() and "pytest tests" not in checks.read_text(encoding="utf-8"):
            problems.append("checks.yml does not run the test suite")

    binaries = ROOT / "src-tauri/binaries"
    if not (binaries / "LGPL-2.1.txt").is_file():
        problems.append("src-tauri/binaries/LGPL-2.1.txt is missing; an LGPL binary may not be distributed without its licence")
    else:
        notes.append("the LGPL text ships beside the binaries")
    if not (binaries / "README-ffmpeg.md").is_file():
        problems.append("src-tauri/binaries/README-ffmpeg.md is missing; the LGPL expects the binary to be replaceable and said so")
    if "ffmpeg" not in text.lower():
        problems.append("Licences.md does not say which ffmpeg build is shipped; a GPL build imposes its terms on the bundle")
    else:
        notes.append("an ffmpeg licence is recorded")
    release = ROOT / "setup/build_release"
    if not release.is_file():
        # check_files has already named it; reading it here would end the run
        # with a traceback instead of a list of problems, and a preflight that
        # crashes tells you less than one that fails.
        return
    workflow = read(release)
    if "--allow-gpl" in workflow or "fetch_ffmpeg" in workflow:
        problems.append(
            "the release build (setup/build_release) fetches an ffmpeg of its own; the app fetches formcut's LGPL build on first run, "
            "and a GPL build in the bundle would make it GPL-3.0 rather than Apache-2.0"
        )
    elif "setup/bundle_ffmpeg.py" in workflow:
        notes.append("the release bundles formcut's own LGPL ffmpeg (setup/bundle_ffmpeg.py), every file checked against the record")
    else:
        notes.append("the release bundles no ffmpeg; the app fetches formcut's LGPL build and checks it against the record")


def check_engine() -> None:
    """The engine has to import before it can be frozen."""
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        from app.main import app
    except Exception as exc:  # noqa: BLE001 - any import failure is the finding here
        problems.append(f"the engine does not import: {exc}")
        return
    notes.append(f"the engine imports, {len(app.routes)} routes mounted")


def check_generated() -> None:
    """Every generated file is current. 1.41.1 shipped a stale skill map, and every
    engine job in checks failed on it, because nothing here asked the generators."""
    import subprocess

    for script in ("skill_maps.py", "mcp_tool_reference.py", "effect_library.py"):
        run = subprocess.run([sys.executable, str(ROOT / "setup" / script), "--check"], capture_output=True, text=True, check=False)
        if run.returncode:
            problems.append(f"{script}: {(run.stdout or run.stderr).strip().splitlines()[0][:160]}")
    run = subprocess.run([sys.executable, str(ROOT / "setup" / "agents.py"), "sync", "--check"], capture_output=True, text=True, check=False)
    if run.returncode:
        problems.append(f"agents.py: {run.stdout.strip()[:160]}")
    notes.append("the skill maps, the MCP tool reference, the .agents skill mirror and the looks library are current")


def main() -> int:
    check_versions()
    check_generated()
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
