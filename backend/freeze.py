import argparse
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import PyInstaller.__main__

parser = argparse.ArgumentParser()
parser.add_argument('--onefile', action='store_true')
args = parser.parse_args()
import cv2
for line in cv2.getBuildInformation().splitlines():
    if (line.strip().startswith("FFMPEG:") or line.strip().startswith("GStreamer:")) and "YES" in line:
        raise SystemExit("Refusing to freeze bundled codec libraries. Run python prepare_cv.py first.")
root = Path(__file__).resolve().parent
lgpl = Path(os.environ.get("LGPL_FFMPEG_PREFIX") or root / ".lgpl-ffmpeg")
os.environ["PATH"] = str(lgpl / "bin") + os.pathsep + os.environ.get("PATH", "")
if subprocess.run([sys.executable, str(root.parent / "setup" / "check_lgpl_av.py"), str(lgpl)]).returncode:
    raise SystemExit("Refusing to freeze PyAV linked to a GPL FFmpeg. Run setup/build_lgpl_av first.")
sys.path.insert(0, str(root.parent / "setup"))
from vendor_av_dlls import ffmpeg_dlls, imports_av

# PyInstaller's PyAV hook imports av in a fresh process; when that fails it only
# warns and freezes an engine without PyAV, so a PyAV that does not import stops here.
if importlib.util.find_spec("av") is not None:
    av_ok, av_detail = imports_av(sys.executable)
    if not av_ok:
        last = av_detail.splitlines()[-1] if av_detail else "no output"
        raise SystemExit(f"Refusing to freeze: PyAV does not import ({last}). Run setup/build_lgpl_av first.")
os.chdir(root)
arguments = [
    '--clean', '--noconfirm', '--name', 'formcut-engine',
    '--onefile' if args.onefile else '--onedir',
    '--add-data', str(root.parent / 'frontend' / 'dist') + os.pathsep + 'frontend_dist',
    '--add-data', str(root.parent / 'src-tauri' / 'binaries' / 'ffmpeg-licence.json') + os.pathsep + '.',
    '--add-data', str(root / 'app' / 'effect_library') + os.pathsep + 'app/effect_library',
    '--add-data', str(root / 'app' / 'bundled_models') + os.pathsep + 'app/bundled_models',
    '--add-data', str(root / 'app' / 'device_library') + os.pathsep + 'app/device_library',
    '--collect-all', 'uvicorn',
    '--collect-binaries', 'wgpu', '--collect-data', 'wgpu',
    '--hidden-import', 'wgpu.backends.wgpu_native', '--hidden-import', 'wgpu.utils.compute',
    '--collect-binaries', 'onnxruntime', '--collect-data', 'onnxruntime',
    '--collect-submodules', 'app', '--hidden-import', 'PIL.ImageFont',
    '--hidden-import', 'PIL.ImageDraw', '--hidden-import', 'PIL.ImageFilter',
    '--hidden-import', 'cv2', '--hidden-import', 'grpc',
    '--exclude-module', 'kokoro_onnx', '--exclude-module', 'phonemizer',
    '--exclude-module', 'espeakng_loader', '--exclude-module', 'torch',
    str(root / 'desktop_entry.py'),
]

# Windows: the FFmpeg DLLs PyAV's .pyd files load, beside them in the engine as in site-packages.
if sys.platform == "win32" and importlib.util.find_spec("av") is not None:
    for dll in ffmpeg_dlls(lgpl):
        arguments.extend(["--add-binary", str(dll) + os.pathsep + "av"])

for package in ("mcp", "mcp-types", "numpy", "Pillow", "opencv-python-headless", "wgpu", "onnxruntime", "fastapi", "uvicorn", "python-multipart", "httpx", "grpcio", "yt-dlp"):
    arguments.extend(["--copy-metadata", package])
for notice in Path(cv2.__file__).parent.glob("LICENSE*"):
    arguments.extend(["--add-data", str(notice) + os.pathsep + "third_party/opencv"])
identity = os.environ.get("APPLE_SIGNING_IDENTITY", "") if sys.platform == "darwin" else ""
if identity:
    arguments.extend(["--codesign-identity", identity, "--osx-entitlements-file", str(root.parent / "src-tauri" / "entitlements.plist")])
PyInstaller.__main__.run(arguments)
