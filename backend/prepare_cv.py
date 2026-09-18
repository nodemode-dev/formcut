import os
import subprocess
import sys

info = subprocess.check_output([sys.executable, "-c", "import cv2; print(cv2.getBuildInformation())"], text=True)


def enabled(name):
    return any(line.strip().startswith(name + ":") and "YES" in line for line in info.splitlines())


if enabled("FFMPEG") or enabled("GStreamer"):
    environment = os.environ.copy()
    environment["CMAKE_ARGS"] = "-DWITH_FFMPEG=OFF -DWITH_GSTREAMER=OFF -DBUILD_LIST=core,imgproc,imgcodecs,features2d,python3 -DWITH_OPENEXR=OFF -DWITH_VTK=OFF -DWITH_QT=OFF -DWITH_GTK=OFF -DWITH_IPP=OFF -DWITH_ITT=OFF"
    environment.setdefault("CMAKE_BUILD_PARALLEL_LEVEL", "4")
    print("Building the permissive image-processing runtime without bundled FFmpeg. A C++ compiler and network access are required.", flush=True)
    subprocess.run([sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", "--no-cache-dir", "--no-binary", "opencv-python-headless", "opencv-python-headless==4.12.0.88"], env=environment, check=True)
    print("Image-processing runtime installed. The freeze step will verify the new build in a fresh process.")
else:
    print("OpenCV has no FFmpeg or GStreamer backend.")
