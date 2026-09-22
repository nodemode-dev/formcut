"""The OpenCV rebuild: what it switches off, and which macOS it builds for.

The rebuild runs on the packager's machine, so it must not depend on what that
machine has installed (Eigen 5 broke it) or on which macOS it runs (a build made
on the newest macOS would not load on any older one).
"""

import importlib
import json
import subprocess
from pathlib import Path

import prepare_cv

ROOT = Path(__file__).resolve().parent.parent


def test_eigen_is_switched_off_with_ffmpeg_and_gstreamer():
    flags = prepare_cv.CMAKE_ARGS.split()
    assert {"-DWITH_EIGEN=OFF", "-DWITH_FFMPEG=OFF", "-DWITH_GSTREAMER=OFF"} <= set(flags)
    assert prepare_cv.build_environment("linux")["CMAKE_ARGS"] == prepare_cv.CMAKE_ARGS


def test_a_macos_build_targets_the_minimum_formcut_declares(monkeypatch):
    monkeypatch.delenv("MACOSX_DEPLOYMENT_TARGET", raising=False)
    declared = json.loads((ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))["bundle"]["macOS"]["minimumSystemVersion"]
    assert prepare_cv.build_environment("darwin")["MACOSX_DEPLOYMENT_TARGET"] == declared == "14.0"


def test_a_target_the_packager_chose_is_kept(monkeypatch):
    monkeypatch.setenv("MACOSX_DEPLOYMENT_TARGET", "13.0")
    assert prepare_cv.build_environment("darwin")["MACOSX_DEPLOYMENT_TARGET"] == "13.0"


def test_other_platforms_get_no_macos_target(monkeypatch):
    monkeypatch.delenv("MACOSX_DEPLOYMENT_TARGET", raising=False)
    for platform in ("linux", "win32"):
        assert "MACOSX_DEPLOYMENT_TARGET" not in prepare_cv.build_environment(platform)


def test_importing_the_script_runs_nothing(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("prepare_cv ran a command on import")

    monkeypatch.setattr(subprocess, "check_output", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    importlib.reload(prepare_cv)
