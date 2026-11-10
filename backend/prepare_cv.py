"""Rebuild OpenCV without FFmpeg or GStreamer, when the installed one has either.

Run by the packaging scripts (python prepare_cv.py) before the engine is frozen,
so the frozen engine carries a permissive image-processing runtime.
"""

import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

# WITH_EIGEN=OFF: OpenCV 4.12 reads Eigen's version from Eigen/src/Core/util/Macros.h,
# and Eigen 5 moved it to Eigen/Version, so on a machine with Eigen 5 installed
# (Homebrew brings it in with other formulae) configure stops with "ocv_add_definition
# Macro invoked with incorrect arguments". The four modules built here do not use
# Eigen, and like FFmpeg and GStreamer the build should not depend on what the build
# machine happens to have installed.
# WITH_AVIF=OFF: imgcodecs finds a Homebrew libavif when the machine has one. On an
# Intel Mac (Homebrew in /usr/local, on CMake's default path) the engine then links a
# library from outside it, and on an Apple Silicon Mac building for Intel it compiles
# against arm64 headers and fails to import ("symbol not found '_avifDecoderCreate'").
# formcut reads no AVIF through OpenCV, so it is off like the others.
CMAKE_ARGS = (
    "-DWITH_FFMPEG=OFF -DWITH_GSTREAMER=OFF -DBUILD_LIST=core,imgproc,imgcodecs,features2d,python3 -DWITH_OPENEXR=OFF"
    " -DWITH_VTK=OFF -DWITH_QT=OFF -DWITH_GTK=OFF -DWITH_IPP=OFF -DWITH_ITT=OFF -DWITH_EIGEN=OFF -DWITH_AVIF=OFF"
)


PACKAGE = "opencv-python-headless"
VERSION = "4.12.0.88"

# opencv-python's setup.py requires the videoio FFmpeg DLL on Windows even when
# FFmpeg is not built, and stops with "Not found: 'bin/opencv_videoio_ffmpeg...'"
# after a successful compile (seen on the Windows release runner). Its check exempts
# only gapi and has no switch, so on Windows the build uses the pinned sdist, checked
# against PyPI's digest, with that one rule removed. Anything but this exact text
# stops the build rather than patching something else.
FFMPEG_DLL_RULE = r"""            [r"bin/opencv_videoio_ffmpeg\d{4}%s\.dll" % ("_64" if is64 else "")]
            if os.name == "nt"
            else []"""


def drop_ffmpeg_dll_rule(setup_text: str) -> str:
    if setup_text.count(FFMPEG_DLL_RULE) != 1:
        raise SystemExit(f"{PACKAGE} {VERSION}'s setup.py no longer has the Windows FFmpeg DLL rule this build removes.")
    return setup_text.replace(FFMPEG_DLL_RULE, "            []")


def windows_source(folder: Path) -> Path:
    """The pinned sdist, verified against PyPI's SHA-256, with the FFmpeg DLL rule removed."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{PACKAGE}/{VERSION}/json", timeout=60) as response:
        release = json.load(response)
    sdist = next(item for item in release["urls"] if item["packagetype"] == "sdist")
    if not sdist["url"].startswith("https://"):
        raise SystemExit(f"PyPI gave a download address that is not https: {sdist['url']}")
    archive = folder / sdist["filename"]
    with urllib.request.urlopen(sdist["url"], timeout=600) as response, archive.open("wb") as out:  # noqa: S310 (https checked above)
        digest = hashlib.sha256()
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            out.write(chunk)
    if digest.hexdigest() != sdist["digests"]["sha256"]:
        raise SystemExit(f"{sdist['filename']} does not match the SHA-256 PyPI publishes for it.")
    with tarfile.open(archive) as tar:
        tar.extractall(folder, filter="data")
    source = folder / f"{PACKAGE}-{VERSION}"
    setup = source / "setup.py"
    setup.write_text(drop_ffmpeg_dll_rule(setup.read_text(encoding="utf-8")), encoding="utf-8")
    return source


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
    pip = [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps"]
    if sys.platform == "win32":
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run([*pip, str(windows_source(Path(folder)))], env=environment, check=True)
    else:
        subprocess.run([*pip, "--no-binary", PACKAGE, f"{PACKAGE}=={VERSION}"], env=environment, check=True)
    print("Image-processing runtime installed. The freeze step will verify the new build in a fresh process.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
