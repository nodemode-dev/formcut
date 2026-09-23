"""H.264 through Cisco's OpenH264, for computers with no H.264 encoder.

formcut's ffmpeg is LGPL, so it carries no software H.264 encoder (x264 is GPL);
it encodes H.264 through the computer's hardware. Where there is none (a Linux
machine with no NVIDIA or VA-API graphics, most often), formcut downloads Cisco's
OpenH264 library the first time an H.264 export needs it, and encodes through it.

Cisco pays the AVC/H.264 patent royalties for its own binary under four
conditions (BINARY_LICENSE below), and formcut meets each: the binary is
downloaded to the person's computer from Cisco, never bundled; Settings lets
them turn its use off and on again; that setting shows NOTICE; and LICENCE is
shown with formcut's licensing information. Each download is checked against
the SHA-256 recorded here, which matches Cisco's signed MD5 for each file.

The library is called directly (ctypes), as its C header lays out, rather than
through an ffmpeg linked to it, which would not start without it. An export
through it renders a lossless FFV1 intermediate by any of the usual paths;
ffmpeg decodes that to I420, the library encodes, and ffmpeg puts the stream
and the audio in the MP4. Without it, an MP4 export falls back to WebM.
"""

from __future__ import annotations

import bz2
import ctypes as C
import hashlib
import json
import platform
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

from .paths import DATA_DIR

VERSION = "2.6.0"
SOURCE = "https://ciscobinary.openh264.org/"
DIR = DATA_DIR / "codecs" / "openh264"
SETTINGS = DATA_DIR / "codecs" / "openh264.json"
NOTICE = "OpenH264 Video Codec provided by Cisco Systems, Inc."

# (sys.platform, machine) -> (Cisco's file, SHA-256 of the library inside)
BINARIES = {
    ("linux", "x86_64"): ("libopenh264-2.6.0-linux64.8.so.bz2", "2f0cde7c6a6abcf5cae76942894ea42897fa677bce4ed6c91a24dd1b041d5f04"),
    ("linux", "aarch64"): ("libopenh264-2.6.0-linux-arm64.8.so.bz2", "12e7b33623667cdab0e575170c147b1b36eadb77d0d2aa7ceb5afd3e58902140"),
    ("darwin", "arm64"): ("libopenh264-2.6.0-mac-arm64.dylib.bz2", "052e98bfcf7a9167d22f3bbb3f5988ef79065591f36af8b52924b22b13624551"),
    ("darwin", "x86_64"): ("libopenh264-2.6.0-mac-x64.dylib.bz2", "e3dc8bc01fe69363f61fd3c02fd27798537a585eadd38cd808f303d1ee505a19"),
    ("win32", "x86_64"): ("openh264-2.6.0-win64.dll.bz2", "2076cb5675ec6c1a4c70e7a2a322552f547b6eeed649d6dfcd9e02a543b24691"),
    ("win32", "arm64"): ("openh264-2.6.0-win-arm64.dll.bz2", "fb75103938f4f47d119b983e06334df41a803bc72fb5c46e3623f6fea5782732"),
}
MACHINES = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64", "aarch64": "aarch64"}


def _binary() -> tuple[str, str] | None:
    machine = MACHINES.get(platform.machine().lower(), platform.machine().lower())
    if sys.platform == "darwin" and machine == "aarch64":
        machine = "arm64"
    if sys.platform == "linux" and machine == "arm64":
        machine = "aarch64"
    return BINARIES.get((sys.platform, machine))


def _local() -> Path | None:
    found = _binary()
    return DIR / found[0].removesuffix(".bz2") if found else None


def enabled() -> bool:
    """On unless the person turned it off: it is only fetched when an export needs it."""
    try:
        return bool(json.loads(SETTINGS.read_text(encoding="utf-8")).get("enabled", True))
    except (OSError, ValueError):
        return True


def set_enabled(value: bool) -> None:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS.write_text(json.dumps({"enabled": bool(value)}), encoding="utf-8")


def _verified(path: Path) -> bool:
    found = _binary()
    return bool(found) and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == found[1]


def status() -> dict:
    local = _local()
    return {
        "supported": local is not None,
        "enabled": enabled(),
        "installed": bool(local and _verified(local)),
        "version": VERSION,
        "notice": NOTICE,
    }


def install() -> Path:
    """Fetch Cisco's library for this computer from Cisco, and keep it only if it is the one recorded."""
    found, local = _binary(), _local()
    if not found or local is None:
        raise RuntimeError("Cisco publishes no OpenH264 library for this computer")
    import httpx

    response = httpx.get(SOURCE + found[0], timeout=120, follow_redirects=True)
    response.raise_for_status()
    library = bz2.decompress(response.content)
    if hashlib.sha256(library).hexdigest() != found[1]:
        raise RuntimeError("The OpenH264 download did not match the library formcut expects, so it was not kept")
    DIR.mkdir(parents=True, exist_ok=True)
    staged = local.with_suffix(local.suffix + ".part")
    staged.write_bytes(library)
    staged.replace(local)
    return local


def remove() -> None:
    local = _local()
    if local:
        local.unlink(missing_ok=True)


def library(download: bool = False) -> Path | None:
    """The library to encode with, fetched now if allowed and needed; None when off, unsupported or unavailable."""
    local = _local()
    if local is None or not enabled():
        return None
    if _verified(local):
        return local
    if not download:
        return None
    try:
        return install()
    except Exception:  # noqa: BLE001  (offline, refused, or not the recorded file: the export falls back)
        return None


# The C interface, from OpenH264 2.6.0's codec_api.h and codec_app_def.h. 2.6.0
# added bPsnrY/U/V to SSourcePicture and rPsnr to SLayerBSInfo; they must be here
# or every layer after the first is read from the wrong place.
class _ParamBase(C.Structure):
    _fields_ = [
        ("iUsageType", C.c_int),
        ("iPicWidth", C.c_int),
        ("iPicHeight", C.c_int),
        ("iTargetBitrate", C.c_int),
        ("iRCMode", C.c_int),
        ("fMaxFrameRate", C.c_float),
    ]


class _Picture(C.Structure):
    _fields_ = [
        ("iColorFormat", C.c_int),
        ("iStride", C.c_int * 4),
        ("pData", C.POINTER(C.c_ubyte) * 4),
        ("iPicWidth", C.c_int),
        ("iPicHeight", C.c_int),
        ("uiTimeStamp", C.c_longlong),
        ("bPsnrY", C.c_bool),
        ("bPsnrU", C.c_bool),
        ("bPsnrV", C.c_bool),
    ]


class _Layer(C.Structure):
    _fields_ = [
        ("uiTemporalId", C.c_ubyte),
        ("uiSpatialId", C.c_ubyte),
        ("uiQualityId", C.c_ubyte),
        ("eFrameType", C.c_int),
        ("uiLayerType", C.c_ubyte),
        ("iSubSeqId", C.c_int),
        ("iNalCount", C.c_int),
        ("pNalLengthInByte", C.POINTER(C.c_int)),
        ("pBsBuf", C.POINTER(C.c_ubyte)),
        ("rPsnr", C.c_float * 3),
    ]


class _Frame(C.Structure):
    _fields_ = [
        ("iLayerNum", C.c_int),
        ("sLayerInfo", _Layer * 128),
        ("eFrameType", C.c_int),
        ("iFrameSizeInBytes", C.c_int),
        ("uiTimeStamp", C.c_longlong),
    ]


def _method(*arguments):
    return C.CFUNCTYPE(C.c_int, C.c_void_p, *arguments)


class _Table(C.Structure):
    _fields_ = [
        ("Initialize", _method(C.POINTER(_ParamBase))),
        ("InitializeExt", _method(C.c_void_p)),
        ("GetDefaultParams", _method(C.c_void_p)),
        ("Uninitialize", _method()),
        ("EncodeFrame", _method(C.POINTER(_Picture), C.POINTER(_Frame))),
        ("EncodeParameterSets", _method(C.POINTER(_Frame))),
        ("ForceIntraFrame", _method(C.c_bool)),
        ("SetOption", _method(C.c_int, C.c_void_p)),
        ("GetOption", _method(C.c_int, C.c_void_p)),
    ]


CAMERA_VIDEO_REAL_TIME, RC_BITRATE_MODE, I420 = 0, 1, 23
OPTION_DATAFORMAT, OPTION_IDR_INTERVAL, OPTION_RC_FRAME_SKIP = 0, 1, 9
FRAME_SKIPPED = 4


class Encoder:
    """One H.264 stream from I420 frames. The real-time usage is the one the plain
    initializer accepts (ffmpeg's wrapper uses it too); frame skipping is off, so
    every frame given is a frame written."""

    def __init__(self, library_path: Path, width: int, height: int, rate: float, bitrate: int, keyframe_every: int):
        self._lib = C.CDLL(str(library_path))
        self._lib.WelsCreateSVCEncoder.argtypes = [C.POINTER(C.c_void_p)]
        self._lib.WelsCreateSVCEncoder.restype = C.c_int
        self._lib.WelsDestroySVCEncoder.argtypes = [C.c_void_p]
        self._handle = C.c_void_p()
        if self._lib.WelsCreateSVCEncoder(C.byref(self._handle)) or not self._handle.value:
            raise RuntimeError("OpenH264 could not create an encoder")
        self._table = C.cast(C.cast(self._handle, C.POINTER(C.c_void_p))[0], C.POINTER(_Table)).contents
        self.width, self.height = width, height
        base = _ParamBase(CAMERA_VIDEO_REAL_TIME, width, height, int(bitrate), RC_BITRATE_MODE, float(rate))
        if self._table.Initialize(self._handle, C.byref(base)):
            self._lib.WelsDestroySVCEncoder(self._handle)
            raise RuntimeError(f"OpenH264 refused {width}x{height} at {rate:g} frames a second")
        for option, value in (
            (OPTION_IDR_INTERVAL, C.c_int(keyframe_every)),
            (OPTION_RC_FRAME_SKIP, C.c_bool(False)),
            (OPTION_DATAFORMAT, C.c_int(I420)),
        ):
            self._table.SetOption(self._handle, option, C.cast(C.byref(value), C.c_void_p))
        self._frames = 0

    def encode(self, i420: bytes | bytearray | memoryview) -> bytes:
        width, height = self.width, self.height
        buffer = (C.c_ubyte * len(i420)).from_buffer_copy(i420)
        start = C.addressof(buffer)
        picture = _Picture(iColorFormat=I420, iPicWidth=width, iPicHeight=height, uiTimeStamp=self._frames)
        for plane, (offset, stride) in enumerate(((0, width), (width * height, width // 2), (width * height * 5 // 4, width // 2))):
            picture.iStride[plane] = stride
            picture.pData[plane] = C.cast(start + offset, C.POINTER(C.c_ubyte))
        info = _Frame()
        if self._table.EncodeFrame(self._handle, C.byref(picture), C.byref(info)):
            raise RuntimeError(f"OpenH264 could not encode frame {self._frames}")
        self._frames += 1
        if info.eFrameType == FRAME_SKIPPED:
            raise RuntimeError(f"OpenH264 skipped frame {self._frames - 1}")
        out = bytearray()
        for index in range(info.iLayerNum):
            layer = info.sLayerInfo[index]
            out += C.string_at(layer.pBsBuf, sum(layer.pNalLengthInByte[n] for n in range(layer.iNalCount)))
        return bytes(out)

    def close(self) -> None:
        if self._handle:
            self._table.Uninitialize(self._handle)
            self._lib.WelsDestroySVCEncoder(self._handle)
            self._handle = C.c_void_p()


def encode_mp4(
    library_path: Path, intermediate: Path, output: Path, width: int, height: int, rate: str, bitrate: int, report, cancelled, log: Path
) -> None:
    """The intermediate's picture through OpenH264 and its sound as AAC, in one MP4."""
    fraction = Fraction(rate).limit_denominator(1001)
    stream = output.with_suffix(".h264")
    frame_size = width * height * 3 // 2
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-count_packets",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_packets",
            "-of",
            "csv=p=0",
            str(intermediate),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    total = max(1, int((probe.stdout.strip() or "1").split(",")[0] or 1))
    encoder = Encoder(library_path, width, height, float(fraction), bitrate, max(1, round(float(fraction) * 2)))
    decode = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-i", str(intermediate), "-map", "0:v:0", "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    try:
        with stream.open("wb") as out:
            done = 0
            while True:
                if cancelled():
                    raise InterruptedError("Cancelled")
                frame = decode.stdout.read(frame_size)
                if len(frame) < frame_size:
                    break
                out.write(encoder.encode(frame))
                done += 1
                report(done / total * 0.95)
        decode.wait(timeout=60)
    finally:
        encoder.close()
        if decode.poll() is None:
            decode.kill()
            decode.wait()
    audio = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(intermediate)],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-f",
        "h264",
        "-r",
        f"{fraction.numerator}/{fraction.denominator}",
        "-i",
        str(stream),
        "-i",
        str(intermediate),
        "-map",
        "0:v:0",
    ]
    command += ["-map", "1:a:0", "-c:a", "aac", "-b:a", "192k"] if audio else []
    command += ["-c:v", "copy", "-video_track_timescale", str(fraction.numerator), "-movflags", "+faststart", str(output)]
    try:
        with log.open("ab") as errors:
            result = subprocess.run(command, stderr=errors, check=False)
        if result.returncode:
            raise ValueError(log.read_text(errors="replace")[-2000:])
    finally:
        stream.unlink(missing_ok=True)
    report(1.0)


LICENCE = """-------------------------------------------------------
About The Cisco-Provided Binary of OpenH264 Video Codec
-------------------------------------------------------

Cisco provides this program under the terms of the BSD license.  

Additionally, this binary is licensed under Cisco’s AVC/H.264 Patent Portfolio License from MPEG LA, at no cost to you, provided that the requirements and conditions shown below in the AVC/H.264 Patent Portfolio sections are met.  

As with all AVC/H.264 codecs, you may also obtain your own patent license from MPEG LA or from the individual patent owners, or proceed at your own risk.  Your rights from Cisco under the BSD license are not affected by this choice.  

For more information on the OpenH264 binary licensing, please see the OpenH264 FAQ found at http://www.openh264.org/faq.html#binary 

A corresponding source code to this binary program is available under the same BSD terms, which can be found at http://www.openh264.org

-----------
BSD License
-----------

Copyright © 2014 Cisco Systems, Inc.

All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS “AS IS” AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

-----------------------------------------
AVC/H.264 Patent Portfolio License Notice
-----------------------------------------

The binary form of this Software is distributed by Cisco under the AVC/H.264 Patent Portfolio License from MPEG LA, and is subject to the following requirements, which may or may not be applicable to your use of this software: 

THIS PRODUCT IS LICENSED UNDER THE AVC PATENT PORTFOLIO LICENSE FOR THE PERSONAL USE OF A CONSUMER OR OTHER USES IN WHICH IT DOES NOT RECEIVE REMUNERATION TO (i) ENCODE VIDEO IN COMPLIANCE WITH THE AVC STANDARD (“AVC VIDEO”) AND/OR (ii) DECODE AVC VIDEO THAT WAS ENCODED BY A CONSUMER ENGAGED IN A PERSONAL ACTIVITY AND/OR WAS OBTAINED FROM A VIDEO PROVIDER LICENSED TO PROVIDE AVC VIDEO.  NO LICENSE IS GRANTED OR SHALL BE IMPLIED FOR ANY OTHER USE.  ADDITIONAL INFORMATION MAY BE OBTAINED FROM MPEG LA, L.L.C. SEE HTTP://WWW.MPEGLA.COM

Accordingly, please be advised that content providers and broadcasters using AVC/H.264 in their service may be required to obtain a separate use license from MPEG LA, referred to as "(b) sublicenses" in the SUMMARY OF AVC/H.264 LICENSE TERMS from MPEG LA found at http://www.openh264.org/mpegla

---------------------------------------------
AVC/H.264 Patent Portfolio License Conditions
---------------------------------------------

In addition, the Cisco-provided binary of this Software is licensed under Cisco's license from MPEG LA only if the following conditions are met:

1. The Cisco-provided binary is separately downloaded to an end user’s device, and not integrated into or combined with third party software prior to being downloaded to the end user’s device;

2. The end user must have the ability to control (e.g., to enable, disable, or re-enable) the use of the Cisco-provided binary;

3. Third party software, in the location where end users can control the use of the Cisco-provided binary, must display the following text:

       "OpenH264 Video Codec provided by Cisco Systems, Inc."

4.  Any third-party software that makes use of the Cisco-provided binary must reproduce all of the above text, as well as this last condition, in the EULA and/or in another location where licensing information is to be presented to the end user.  
 


                          v1.0
"""
