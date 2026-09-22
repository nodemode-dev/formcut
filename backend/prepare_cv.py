"""Rebuild OpenCV without FFmpeg or GStreamer, when the installed one has either.

Run by the packaging scripts (python prepare_cv.py) before the engine is frozen,
so the frozen engine carries a permissive image-processing runtime.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# WITH_EIGEN=OFF: OpenCV 4.12 reads Eigen's version from Eigen/src/Core/util/Macros.h,
# and Eigen 5 moved it to Eigen/Version, so on a machine with Eigen 5 installed
# (Homebrew brings it in with other formulae) configure stops with "ocv_add_definition
# Macro invoked with incorrect arguments". The four modules built here do not use
# Eigen, and like FFmpeg and GStreamer the build should not depend on what the build
# machine happens to have installed.
CMAKE_ARGS = (
    "-DWITH_FFMPEG=OFF -DWITH_GSTREAMER=OFF -DBUILD_LIST=core,imgproc,imgcodecs,features2d,python3 -DWITH_OPENEXR=OFF"
    " -DWITH_VTK=OFF -DWITH_QT=OFF -DWITH_GTK=OFF -DWITH_IPP=OFF -DWITH_ITT=OFF -DWITH_EIGEN=OFF"
)


def macos_floor() -> str:
    """formcut's minimum macOS, as src-tauri/tauri.conf.json declares it."""
    config = Path(__file__).resolve().parent.parent / "src-tauri" / "tauri.conf.json"
    try:
        return json.loads(config.read_text(encoding="utf-8"))["bundle"]["macOS"]["minimumSystemVersion"]
    except (OSError, KeyError, ValueError):
        return "12.0"


def build_environment(platform: str = sys.platform) -> dict:
    environment = os.environ.copy()
    environment["CMAKE_ARGS"] = CMAKE_ARGS
    environment.setdefault("CMAKE_BUILD_PARALLEL_LEVEL", "4")
    if platform == "darwin":
        # scikit-build targets the macOS the build runs on unless told otherwise, so a
        # build made on the newest macOS would refuse to load on any older one.
        environment.setdefault("MACOSX_DEPLOYMENT_TARGET", macos_floor())
    return environment


def enabled(info: str, name: str) -> bool:
    return any(line.strip().startswith(name + ":") and "YES" in line for line in info.splitlines())


def main() -> int:
    info = subprocess.check_output([sys.executable, "-c", "import cv2; print(cv2.getBuildInformation())"], text=True)
    if not (enabled(info, "FFMPEG") or enabled(info, "GStreamer")):
        print("OpenCV has no FFmpeg or GStreamer backend.")
        return 0
    environment = build_environment()
    target = environment.get("MACOSX_DEPLOYMENT_TARGET")
    notice = "Building the permissive image-processing runtime without bundled FFmpeg. A C++ compiler and network access are required."
    print(notice, flush=True)
    if target:
        print(f"It will run on macOS {target} and later.", flush=True)
    package = "opencv-python-headless==4.12.0.88"
    pip = [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", "--no-cache-dir"]
    subprocess.run([*pip, "--no-binary", "opencv-python-headless", package], env=environment, check=True)
    print("Image-processing runtime installed. The freeze step will verify the new build in a fresh process.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
