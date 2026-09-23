"""The release workflow: when it builds, what it builds, and what it publishes.

It cannot run here, so its rules are checked from the file: only the maintainer
starts it, by hand and from main; it builds only a version with no tag yet unless
asked to rebuild, every platform is checked and packaged the same way,
nothing is published unless every build succeeded, and the notes name exactly the
zips setup/package_release.py writes.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = yaml.safe_load((ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8"))
JOBS = WORKFLOW["jobs"]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "setup" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _targets() -> list[str]:
    return [entry["target"] for entry in JOBS["build"]["strategy"]["matrix"]["include"]]


def _runs(job: str) -> str:
    return "\n".join(step.get("run", "") for step in JOBS[job]["steps"])


def test_only_a_hand_run_from_main_starts_it():
    triggers = WORKFLOW[True]  # YAML reads the key "on" as true
    assert set(triggers) == {"workflow_dispatch"}, "no push, tag or schedule may start a release"
    rebuild = triggers["workflow_dispatch"]["inputs"]["rebuild"]
    assert rebuild["type"] == "boolean" and rebuild["default"] is False
    assert 'if [ "$GITHUB_REF" != "refs/heads/main" ]' in _runs("version")


def test_only_a_version_without_a_tag_builds():
    assert "refs/tags/v$version" in _runs("version")
    for job in ("build", "publish"):
        assert JOBS[job]["if"] == "needs.version.outputs.build == 'true'"


def test_the_three_platforms_it_ships():
    assert _targets() == ["aarch64-apple-darwin", "x86_64-pc-windows-msvc", "x86_64-unknown-linux-gnu"]


def test_every_platform_is_checked_bundled_and_packaged_alike():
    runs = _runs("build")
    assert '"native_kernels": true' in runs
    assert "setup/bundle_ffmpeg.py" in runs
    assert "setup/package_release.py" in runs
    assert any(step.get("uses", "").startswith("actions/upload-artifact") for step in JOBS["build"]["steps"])


def test_nothing_is_published_unless_every_build_succeeded():
    assert JOBS["publish"]["needs"] == ["version", "build", "android", "ios"]
    runs = _runs("publish")
    assert "setup/release_notes.py" in runs and "gh release create" in runs and "--clobber" in runs
    assert "setup/release_manifest.py" in runs and "SHA256SUMS" in runs and "release-dist/*" in runs


def test_the_notes_name_exactly_the_zips_that_are_built():
    packager, notes = _load("package_release"), _load("release_notes")
    text = notes.notes("9.9.9")
    for target in _targets():
        platform, arch = packager.PLATFORMS[target]
        assert f"`formcut-9.9.9-{platform}-{arch}.zip`" in text


def test_the_phone_apps_are_built_unsigned_and_gate_the_release():
    jobs = JOBS
    assert set(jobs["publish"]["needs"]) >= {"build", "android", "ios"}
    android = " ".join(step.get("run", "") for step in jobs["android"]["steps"])
    ios = " ".join(step.get("run", "") for step in jobs["ios"]["steps"])
    assert "tauri android build --debug --apk --target aarch64" in android and "android-arm64.apk" in android
    assert "tauri ios build --no-sign --target aarch64" in ios and "ios-arm64.ipa" in ios
    for job in ("android", "ios"):
        assert jobs[job]["env"]["VERSION"] == "${{ needs.version.outputs.version }}"
