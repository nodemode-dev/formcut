import argparse
import os
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

for package in ("mcp", "mcp-types", "numpy", "Pillow", "opencv-python-headless", "wgpu", "onnxruntime", "fastapi", "uvicorn", "python-multipart", "httpx", "grpcio", "yt-dlp"):
    arguments.extend(["--copy-metadata", package])
for notice in Path(cv2.__file__).parent.glob("LICENSE*"):
    arguments.extend(["--add-data", str(notice) + os.pathsep + "third_party/opencv"])
PyInstaller.__main__.run(arguments)
