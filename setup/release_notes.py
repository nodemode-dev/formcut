#!/usr/bin/env python3
"""Write a formcut release's notes, as the release workflow publishes them.

    python setup/release_notes.py --version 1.32.0 > notes.md

A download table, how to open each platform's zip, and what changed: the commit
subjects since the previous v* tag, or the latest ones for the first release.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIRST_RELEASE_LIMIT = 40


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()


def changes(version: str) -> tuple[list[str], str | None]:
    tags = [tag for tag in git("tag", "--list", "v*", "--sort=-v:refname").splitlines() if tag != f"v{version}"]
    previous = tags[0] if tags else None
    span = f"{previous}..HEAD" if previous else "HEAD"
    subjects = git("log", "--format=%s", "--no-merges", span).splitlines()
    return subjects, previous


def notes(version: str) -> str:
    subjects, previous = changes(version)
    name = f"formcut-{version}"
    lines = [
        f"# formcut {version}",
        "",
        "A self-contained build for each platform formcut ships on. Every zip runs with nothing else installed;",
        "formcut's LGPL ffmpeg is inside, checked file by file against the record formcut carries.",
        "",
        "## Download",
        "",
        "| Platform | File |",
        "| --- | --- |",
        f"| macOS, Apple silicon | `{name}-macos-arm64.zip` |",
        f"| Windows, x86_64 | `{name}-windows-x86_64.zip` |",
        f"| Linux, x86_64 | `{name}-linux-x86_64.zip` |",
        f"| Android, arm64 | `{name}-android-arm64.apk` |",
        f"| iOS, arm64 | `{name}-ios-arm64.ipa` |",
        "",
        "- **macOS 14 or later:** unzip and open formcut.app. It is signed but not notarized, so the",
        "  first time macOS says it cannot verify formcut: open System Settings, Privacy & Security,",
        "  and choose Open Anyway beside formcut.",
        "- **Windows 10 or 11:** unzip and run formcut.exe from the formcut folder, keeping",
        "  formcut-engine.exe and the ffmpeg folder beside it. SmartScreen may warn about an unsigned",
        "  app: choose More info, then Run anyway.",
        "- **Linux with glibc 2.35 or later** (Ubuntu 22.04, Debian 12, Fedora 36 and newer): unzip and",
        "  run the AppImage.",
        "- **Intel Macs:** build it with `setup/build_macos_app --intel` on any Mac.",
        "- **Android 7.0 or later:** open the APK on the phone and allow installing apps from that source. It is signed",
        "  with Android's debug key, not a release key.",
        "- **iOS 14 or later:** the IPA is unsigned; install it with AltStore, SideStore or Sideloadly, which sign it",
        "  with your Apple ID. With a free Apple ID, reinstall it every 7 days.",
        "- The phone apps are companions: pair them with formcut running on your computer, over your own network.",
        "",
        "Check a download against `SHA256SUMS` (`shasum -a 256 -c SHA256SUMS` on macOS, `sha256sum -c SHA256SUMS`",
        "on Linux); `manifest.json` lists each file with its size, SHA-256 and minimum OS.",
        "",
        "## What changed",
        "",
    ]
    shown = subjects if previous else subjects[:FIRST_RELEASE_LIMIT]
    lines += [f"- {subject}" for subject in shown] or ["- (no commits since the previous release)"]
    if not previous and len(subjects) > FIRST_RELEASE_LIMIT:
        lines.append(f"- and {len(subjects) - FIRST_RELEASE_LIMIT} earlier changes: the first release")
    if previous:
        lines += ["", f"Since {previous}."]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", required=True)
    print(notes(parser.parse_args().version), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
