# LICENSES · formcut

Ledger per dev-rules and the tauri pack's sidecar-tier policy. Distribution axis: the desktop bundle is distributed; the engine ships inside it, external binaries do not.

## Runtime dependencies (ship in the bundle)

| Component | License | Role | Decision |
| --- | --- | --- | --- |
| fastapi | MIT | engine web framework | ship |
| uvicorn | BSD-3-Clause | engine server | ship |
| python-multipart | Apache-2.0 | upload parsing | ship |
| vite, typescript | MIT | build-time only, output ships | ship |
| Inter font | OFL-1.1 | No remote stylesheet or font file is shipped; system UI fonts are used | not bundled |
| httpx | BSD-3-Clause | Pexels API and media fetch | ship |
| yt-dlp | Unlicense (public domain) | URL media import, invoked as a module subprocess | ship |
| @huggingface/transformers | Apache-2.0 | in-browser Whisper transcription | ship |
| tauri, tauri-build | MIT OR Apache-2.0 | shell | ship |
| tauri-plugin-shell | MIT OR Apache-2.0 | sidecar spawn | ship |
| tauri-plugin-dialog | MIT OR Apache-2.0 | failure dialog | ship |
| regex (crate) | MIT OR Apache-2.0 | port line matching | ship |

## Build tools (never ship)

| Component | License | Decision |
| --- | --- | --- |
| PyInstaller | GPL-2.0 with bootloader exception | build tool only; the exception explicitly permits distributing frozen output under any terms |
| icnsutil | MIT | build-time convenience used once to pre-generate icon.icns in-repo; the build scripts regenerate the full set with cargo tauri icon |

## External tier-1 binaries (user-supplied, never bundled)

| Component | License | Decision |
| --- | --- | --- |
| ffmpeg, ffprobe | LGPL or GPL depending on the build shipped, see below | External processes; on PATH when run from source, inside the bundle from a release. Video decoding, probing, audio processing and export use these executables. Distribution builds reject OpenCV wheels with bundled FFmpeg/GStreamer backends; prepare_cv.py builds image processing without them. |

## OpenH264 (downloaded from Cisco when needed, never bundled)

formcut's ffmpeg is LGPL and has no software H.264 encoder. On a computer with no H.264 encoder of its own, formcut downloads Cisco's OpenH264 library (version 2.6.0, BSD-2-Clause) from `ciscobinary.openh264.org` the first time an H.264 export needs it, checks it against the SHA-256 recorded in `backend/app/openh264.py` (each matching Cisco's signed MD5), and encodes through it. Cisco pays the AVC/H.264 patent royalties for its own binary under four conditions, and formcut meets each:

1. It is downloaded to the person's computer from Cisco when needed, and never bundled with formcut.
2. Settings, Advanced, "H.264 without a hardware encoder" turns its use off and on again.
3. That setting shows "OpenH264 Video Codec provided by Cisco Systems, Inc."
4. The whole licence text is shown there (Licence), and below.

Cisco's patent licence covers personal use and uses that earn no money; the setting says so. Where it is turned off or cannot be fetched, MP4 exports are saved as WebM.

```text
-------------------------------------------------------
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
```

## ffmpeg in a release bundle

formcut is **Apache-2.0** and stays Apache-2.0 in a release, because it runs
ffmpeg as a **separate program** rather than linking against it. The two meet at
a process boundary, and neither licence reaches across it.

The builds are **LGPL-2.1** (`--disable-gpl --disable-nonfree`), published one
archive per target on the formcut-binaries release. The macOS, Windows and
Linux release zips carry the build for their platform, checked file by file
against the SHA-256 recorded in `ffmpeg-licence.json` when the release is made
(`setup/bundle_ffmpeg.py`). Any machine where no ffmpeg is found, such as a run
from source, fetches the archive on first run and checks it the same way,
against the record the app carries; if one file
differs, nothing is installed. A GPL ffmpeg inside the bundle would make the
distributed whole GPL-3.0, so preflight fails any release workflow that passes
`--allow-gpl` or uses the retired fetch script.

Three things ship beside the binary, and all three are required rather than
courtesies:

| File | Why |
| --- | --- |
| `LGPL-2.1.txt` | the licence itself, as the LGPL requires |
| `ffmpeg-licence.json` | version, configure line, programs and SHA-256 of what was shipped |
| `README-ffmpeg.md` | how to replace the binary, per platform |

**Replacement is the point.** The LGPL exists so a person can substitute their
own build of the library, and a bundle that made that difficult would satisfy
the letter and miss the purpose. formcut puts its `binaries` folder at the front
of its search path, so a replaced binary is the one that runs, everywhere,
without rebuilding anything. On macOS that is *Show Package Contents* and
`Contents/Resources/binaries/`. `FORMCUT_FFMPEG_DIR` points it elsewhere
entirely.

**libx264 is GPL, so an LGPL ffmpeg has no software H.264 encoder.** That is not
a flag to flip: including x264 makes the bundle GPL. formcut copes because its
encoder detection prefers hardware and confirms each candidate by encoding two
frames rather than trusting a list, so videotoolbox on macOS, mediafoundation
or nvenc on Windows and vaapi or nvenc on Linux are used where present.
`setup/build_ffmpeg_lgpl.sh` also links openh264 (BSD), libvpx and libaom when
they are installed, so a machine with no hardware encoder still has a non-GPL
software path for H.264, VP9 and AV1.

**ffprobe.** An LGPL build made with `--disable-programs --enable-ffmpeg`
contains ffmpeg alone, since ffprobe is a separate program. formcut does not
require one: when ffprobe is absent it reads the same facts from ffmpeg's own
report, verified to agree on dimensions, codec, duration and frame rate. An
LGPL ffprobe placed in the folder is used in preference.

## Icons and assets

All UI icons are hand-authored inline currentColor SVG in this repo, except the timeline and track glyph family in frontend/src/ui/icons-lucide.ts, which is generated from the Lucide set (ISC licence) of the bundled IcoLab library: 22 keys, default style, 24-unit grid, currentColor bodies with stroke weight left to the caller. ISC requires the copyright notice be retained, which travels with the set; no attribution is displayed in the UI and no icon package is a dependency. The brand glyph, favicon, PWA icons and Tauri icon set derive from the owner-supplied formcut icon (src-tauri/icons/formcut-icon.svg). The demo media in examples/demo are tracked in the repository and keep their own licences, listed in [examples/demo/README.md](https://github.com/nodemode-ai/formcut/blob/main/examples/demo/README.md): the two clips (input-clip-example.mp4, model-drop-MV.mp4) and the image (effect-example-image.jpg) are from Pexels under the Pexels License, and the spoken line (a-sample.wav) was generated for formcut with Kokoro-82M (Apache-2.0). They are not covered by formcut's Apache-2.0 licence. examples/demo is not bundled into frozen builds.

## Implementation dependencies

| Component | License | Distribution decision |
| --- | --- | --- |
| NumPy 2.2.x | BSD-3-Clause; wheel includes its own third-party notices | Engine dependency; preserve distribution metadata |
| Pillow 11.x | HPND; bundled codecs have separate notices | Engine image/text dependency; preserve distribution metadata |
| OpenCV 4.12.0.88 headless | Apache-2.0; upstream wheel codec libraries have additional licenses | Source-build core/imgproc/imgcodecs/features2d/python3 with FFmpeg, GStreamer and GUI backends disabled before freezing |
| wgpu-py 0.31.1 / wgpu-native | BSD-2-Clause / MIT OR Apache-2.0 | GPU composition and custom shaders; preserve package notices |
| ONNX Runtime 1.23.2 | MIT | Local segmentation inference; preserve package notices |
| pi-heif 1.x | BSD-3-Clause package; wheel bundles libheif and libde265, both LGPL-3.0, as dynamically linked libraries, decoders only, no encoder | HEIC and HEIF decoding for import (X6); LGPL separability holds because the .so files are replaceable, the same ground the bundled ffmpeg stands on; the full pillow-heif is excluded because its wheels carry encoders |
| grpcio | Apache-2.0 | Optional headless transport |
| U2Net / U2NetP weights | Apache-2.0 upstream project | Explicit download into user data; never bundled |
| Kokoro 82M model | Apache-2.0 upstream model card | Explicit download into user data; never bundled |
| Pocket TTS (Kyutai) | MIT code; CC-BY-4.0 weights, credited to Kyutai; the voice-cloning weights are gated behind Kyutai's terms, which forbid cloning without consent | Installed into the speech runtime on request; weights downloaded into user data; never bundled |
| Chatterbox (Resemble AI) | MIT code and weights; every output carries Resemble AI's inaudible Perth watermark | Installed into the speech runtime on request; weights downloaded into user data; never bundled |
| Real-ESRGAN x4plus weights (ONNX export) | BSD-3-Clause (xinntao/Real-ESRGAN) | Explicit download into user data from the AI upscale dialog, checked against its pinned SHA-256; never bundled |
| kokoro-onnx | MIT wrapper; phonemizer/eSpeak dependencies include GPL terms | External user-installed speech environment only; wrapper, phonemizer and eSpeak excluded from the frozen engine |

Licence sources: [OpenCV packaging](https://github.com/opencv/opencv-python), [Pillow](https://github.com/python-pillow/Pillow), [NumPy](https://github.com/numpy/numpy), [wgpu-py](https://github.com/pygfx/wgpu-py), [wgpu](https://github.com/gfx-rs/wgpu), [ONNX Runtime](https://github.com/microsoft/onnxruntime), [gRPC](https://github.com/grpc/grpc), [U2Net](https://github.com/xuebinqin/U-2-Net), [Kokoro model](https://huggingface.co/hexgrad/Kokoro-82M), [Kokoro ONNX wrapper](https://github.com/thewh1teagle/kokoro-onnx).

The packaging audit found libavcodec/libavformat/libavutil/libswscale in the initial standard OpenCV diagnostic freeze. That output is not a distributable. VideoSource now decodes through external FFmpeg, and freeze.py rejects a codec-enabled OpenCV runtime. Native platform dependency audits remain required on their actual built bundles. No frozen binary or third-party wheel is included in this source release.

## Background removal model candidates (BG1 gate, v0.60.0)

The gate exists so no model reaches the build before its licence is recorded. A
candidate may only be bundled or downloaded once its row carries a licence that
permits redistribution and a SHA-256 taken from the file we actually ship.

| Role | Candidate | Licence | Source | Bundle or download | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| Selfie segmentation, bundled (BG2) | MediaPipe Selfie Segmentation (tflite/onnx export, under 1 MB) | Apache-2.0 | https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite | bundle in the engine build | pending, recorded on first fetch |
| Video matting, person (BG4) | MODNet | Apache-2.0 | https://github.com/ZHKKKe/MODNet | download on demand | pending, recorded on first fetch |
| Object matting (BG4) | IS-Net (DIS), general use | Apache-2.0 | https://github.com/xuebinqin/DIS | download on demand | pending, recorded on first fetch |
| Object matting, alternative (BG4) | BiRefNet | MIT | https://github.com/ZhengPeng7/BiRefNet | download on demand | pending, recorded on first fetch |
| Prompted region segmentation, brush (BG5) | MobileSAM | Apache-2.0 | https://github.com/ChaoningZhang/MobileSAM | download on demand | pending, recorded on first fetch |
| Prompted region segmentation, alternative (BG5) | SlimSAM | Apache-2.0 | https://github.com/czg1225/SlimSAM | download on demand | pending, recorded on first fetch |

Excluded by policy, recorded so the decision is not revisited by accident:

| Model | Licence | Why excluded |
| --- | --- | --- |
| RobustVideoMatting (RVM) | GPL-3.0 | copyleft, incompatible with shipping inside a proprietary bundle |
| U2Net full weights from some mirrors | unclear or unstated | provenance not verifiable; the Apache-2.0 rembg release is used instead |
| SAM (original, Meta) | Apache-2.0 code, weights under a separate research licence | weight licence does not permit redistribution here |

Each SHA-256 stays "pending" until the file is fetched on a networked machine and
hashed with `shasum -a 256`, and the value is written back into this table in the
same change that adds the model to `backend/app/model_manager.py`. That ordering
is the gate: no entry in the model manager without a hash in this row.
