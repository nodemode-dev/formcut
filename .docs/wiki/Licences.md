# LICENSES · formcut

Ledger per dev-rules and the tauri pack's sidecar-tier policy. Distribution axis: the desktop bundle is distributed; the engine ships inside it, external binaries do not.

## Runtime dependencies (ship in the bundle)

| Component | License | Role | Decision |
| --- | --- | --- | --- |
| fastapi | MIT | engine web framework | ship |
| uvicorn | BSD-3-Clause | engine server | ship |
| python-multipart | Apache-2.0 | upload parsing | ship |
| Form Extension Contract kit (nodemode) | Apache-2.0 | extension host: backend/app/formext_host.py and frontend/src/extensions/host-bridge.ts, vendored unchanged | ship |
| vite, typescript | MIT | build-time only, output ships | ship |
| Inter font | OFL-1.1 | No remote stylesheet or font file is shipped; system UI fonts are used | not bundled |
| 3d-mock-models device library v0.10.0 | CC0-1.0 | ten device models in backend/app/device_library (generated in code by the owner's 3d-mock-models; LICENSE beside them) | ship |
| Inter glyphs in the device key legends | OFL-1.1 | drawn into the laptop and 2-in-1 models' legend textures by the generator; images only, no font file | ship |
| httpx | BSD-3-Clause | Pexels API and media fetch | ship |
| yt-dlp | Unlicense (public domain) | URL media import, invoked as a module subprocess | ship |
| @huggingface/transformers | Apache-2.0 | in-browser Whisper transcription | ship |
| onnxruntime-web 1.31.0-dev.20260914 (with onnxruntime-common 1.30.0 and flatbuffers) | MIT; flatbuffers Apache-2.0 | the runtime transformers.js uses for Whisper in the window, including its WebAssembly files | ship |
| PyAV 18.1.0 (`av`) | BSD-3-Clause | in-process video decoding (`backend/app/video_source.py`); the release builds it from source with `setup/build_lgpl_av`, never the PyPI wheel, which links GPL x264 and x265; `backend/freeze.py` refuses to freeze a PyAV linked to anything else | ship |
| FFmpeg 8.0.3 libraries for PyAV (libavcodec, libavformat, libavutil, libavfilter, libavdevice, libswscale, libswresample) | LGPL-2.1-or-later | the unmodified `https://ffmpeg.org/releases/ffmpeg-8.0.3.tar.xz` (SHA-256 `6136812ea6d4e68bdba27e33c2a94382711cdf4f8602ffef056ff792bd6f9818`), configured with `--disable-gpl --disable-nonfree --disable-version3 --disable-autodetect` and only zlib and, on macOS, VideoToolbox and AudioToolbox, or on Windows D3D11VA and DXVA2; separate shared libraries. `setup/release_assets` attaches this tarball, and the sidecar's FFmpeg 7.1.5 tarball, to every release | ship |
| Android app (`setup/build_phone android`): the Gradle project `tauri android init` generates, with AndroidX (appcompat, activity, webkit), Material Components and the Kotlin standard library | Apache-2.0 | the phone build; the iOS app uses the system WebKit | ship (phone builds) |
| @xterm/xterm, @xterm/addon-fit | MIT | the agent terminal pane in Studio | ship |
| tauri, tauri-build | MIT OR Apache-2.0 | shell | ship |
| tauri-plugin-shell | MIT OR Apache-2.0 | sidecar spawn | ship |
| tauri-plugin-dialog | MIT OR Apache-2.0 | failure dialog | ship |
| regex (crate) | MIT OR Apache-2.0 | port line matching | ship |
| cssparser, selectors, dtoa-short, option-ext (crates) | MPL-2.0 | Tauri's HTML handling (tauri-utils), linked unedited, source at crates.io | ship |
| r-efi (crate) | MIT OR Apache-2.0 OR LGPL-2.1-or-later | used under MIT | ship |
| WebKitGTK, GTK, GLib (Linux AppImage) | LGPL-2.1-or-later | the build machine's shared libraries the AppImage carries | ship |

The installers carry `LICENSE`, `NOTICE` and this page (`bundle.resources`).

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

All UI icons are hand-authored inline currentColor SVG in this repo, except the timeline and track glyph family in frontend/src/ui/icons-lucide.ts, which is generated from the Lucide set (ISC licence) of the bundled IcoLab library: 22 keys, default style, 24-unit grid, currentColor bodies with stroke weight left to the caller. ISC requires the copyright notice be retained, which travels with the set; no attribution is displayed in the UI and no icon package is a dependency. The favicon, PWA icons and Tauri icon set derive from the owner-supplied formcut icon (src-tauri/icons/formcut-icon.svg); the in-app brand glyph in frontend/src/ui/icons.ts keeps its earlier currentColor drawing. The demo media in examples/demo are tracked in the repository and keep their own licences, listed in [examples/demo/README.md](https://github.com/nodemode-ai/formcut/blob/main/examples/demo/README.md): the two clips (input-clip-example.mp4, model-drop-MV.mp4) and the image (effect-example-image.jpg) are from Pexels under the Pexels License, and the spoken line (a-sample.wav) was generated for formcut with Kokoro-82M (Apache-2.0). They are not covered by formcut's Apache-2.0 licence. Since 2.12.6 the four files ship inside the frozen engine (backend/freeze.py) for the first-run demo, and NOTICE credits each one with its creator, source and licence. The browser demo in demo/ has its own media, separate from examples/demo: eight Pexels clips (Pexels License) and the Aria of Bach's Goldberg Variations as played by Kimiko Ishizaka (CC0 1.0), listed file by file with author, source page and changes in [demo/CREDITS.md](https://github.com/nodemode-ai/formcut/blob/main/demo/CREDITS.md). They are not covered by formcut's Apache-2.0 licence and stay out of the desktop app. The two further browser demos have their own media: [demos/grade](https://github.com/nodemode-ai/formcut/blob/main/demos/grade/CREDITS.md) carries six Pexels clips (Pexels License) and a Goldberg Variation by Kimiko Ishizaka (CC0 1.0), and [demos/deliver](https://github.com/nodemode-ai/formcut/blob/main/demos/deliver/CREDITS.md) carries eight Pexels clips, a LibriVox reading of Thoreau's Walden by Gord Mackenzie (public domain) and a Goldberg Variation (CC0 1.0), each file listed with author, source page and changes. They are not covered by formcut's Apache-2.0 licence and stay out of the desktop app.

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
| kokoro-onnx | MIT wrapper; phonemizer/eSpeak dependencies include GPL terms | External user-installed speech environment only; wrapper, phonemizer and eSpeak excluded from the frozen engine. A source checkout whose own interpreter has it runs the voice in-process (v1.74.0); the frozen app never carries it, which is why the second environment exists |

Licence sources: [OpenCV packaging](https://github.com/opencv/opencv-python), [Pillow](https://github.com/python-pillow/Pillow), [NumPy](https://github.com/numpy/numpy), [wgpu-py](https://github.com/pygfx/wgpu-py), [wgpu](https://github.com/gfx-rs/wgpu), [ONNX Runtime](https://github.com/microsoft/onnxruntime), [gRPC](https://github.com/grpc/grpc), [U2Net](https://github.com/xuebinqin/U-2-Net), [Kokoro model](https://huggingface.co/hexgrad/Kokoro-82M), [Kokoro ONNX wrapper](https://github.com/thewh1teagle/kokoro-onnx).

The packaging audit found libavcodec/libavformat/libavutil/libswscale in the initial standard OpenCV diagnostic freeze. That output is not a distributable. VideoSource now decodes through external FFmpeg, and freeze.py rejects a codec-enabled OpenCV runtime. Native platform dependency audits remain required on their actual built bundles. No frozen binary or third-party wheel is included in this source release.

## Background removal and local model registry (BG1 gate; completed at v1.58.0)

The gate exists so no model reaches the build before its licence is recorded. A
model may only be registered once its row carries a licence that permits the
offering and a SHA-256 taken from the file we actually fetched. Every registry
entry in `backend/app/model_manager.py` is pinned in its `PINNED` table to the
hash below; a download that does not match its pin is deleted and named.

| Registry entry | Model | Licence | Offering | SHA-256 |
| --- | --- | --- | --- | --- |
| video-matting | Robust Video Matting (mobilenetv3 fp32) | GPL-3.0-only | download at the person's explicit request, never bundled; see the note below | 88d4531297118f595bf2fd60f6f566aec2e559393802d1f436c380f0cbbd2828 |
| sharp-cutout | IS-Net general use (rembg release) | Apache-2.0 | download on demand | 60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a |
| click-select | SAM 2 Hiera Tiny encoder / decoder (ONNX export) | Apache-2.0 | download on demand | 4cc015ee18520e93f8c7ddfeaca7436039daaaaf19721b4b96a8810a805e82f7 / f5a4bd656c143899fb7f52d64ed81e6f6aeb37d477a0b6da50146ac7cf2187bf |
| click-track | SAM 2.1 Tiny video (vision encoder / mask decoder / memory encoder / memory attention / pointer tpos / constants) | Apache-2.0 | download on demand | aa7a8542942f042e235a993a1ab0ccf5f049918500577802a7f10ec1b39bb873 / 0461896de3db00936fe1643506f129d71cb6d5d2ae15754811756b7ea1b070c6 / 580d246c109de88838f600ba7c1c0d03d1fe267f7641b06f8c88c5f0dc5834cd / 791e648ce8f5ef91ad00ba06e83066ff261ae5a645f0b042b4f46a89fd054baf / 7e71df1d75dba09bc18dd4ae745c2a2cceebdd14d84eadea2fe65d0205f101fc / 172edc70e892aab0aef6caedf97b8e4091fbf6c5d26dac5fd9ea69d093d927d3 |
| object-cutout | U2NetP (rembg release) | Apache-2.0 | download on demand, and bundled in the engine build as the out-of-the-box cutout (BG2, below) | 309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8 |
| person-cutout | U2Net human segmentation (rembg release) | Apache-2.0 | download on demand | 01eb6a29a5c4d8edb30b56adad9bb3a2a0535338e480724a213e0acfd2d1c73c |
| ai-upscale | Real-ESRGAN x4plus (ONNX export) | BSD-3-Clause | download on demand | 4851ec156207d271f5328605d0582eeb851e656227da8aca093ced9e60789291 |
| krea-2-mlx-q8 | Krea 2 Turbo, 8-bit MLX (mflux-community/krea-2-turbo-mflux-q8) | Krea 2 Community License Agreement v.1 | optional; fetched from its publisher only from the Krea 2 card, after the licence is accepted, with the content filter | each of 19 files pinned in model_manager.PINNED |
| krea-2-mlx-q4 | Krea 2 Turbo, 4-bit MLX (mflux-community/krea-2-turbo-mflux-q4) | Krea 2 Community License Agreement v.1 | as above | each of 16 files pinned |
| krea-2-sdnq-int8 | Krea 2 Turbo, 8-bit SDNQ (OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit) | Krea 2 Community License Agreement v.1 | as above | each of 14 files pinned |
| nsfw-filter | Falconsai/nsfw_image_detection (onnx-community ONNX export) | Apache-2.0 | installed with every Krea 2 build as the content filter its licence requires (section 4.2) | each of 4 files pinned |
| local-speech | Kokoro v1.0 model / voices | Apache-2.0 | download on demand | beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a / bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d |
| local-image | SD Turbo ONNX export (onnxruntime/sd-turbo at 80d4d2e238a7c61a83053b931f2354ab43dd3688) | Stability AI Non-Commercial Research Community License | optional: downloaded only from its own button after the licence is shown, never by `FORMCUT_MODELS_AUTO=all`, never bundled | each of 10 files pinned |
| voice-activity | Silero VAD v6.2.3 (commit 5cd7945676eb32225748052e2e6a0580e4686a08) | MIT | download on demand | 1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3 |
| Whisper (hub) | Whisper tiny, base, small, medium (English and multilingual) and large-v3-turbo, ONNX exports by Xenova and onnx-community, each at one pinned revision | MIT (OpenAI's weights); Apache-2.0 on the Xenova cards | fetched through `/api/models/hub` when the transcriber first asks; only the 7 files each uses, each pinned (`HUB_PINNED`) | 63 files pinned |

Since 2.9.4 `download()` refuses a built-in file that has no pin, and the hub answers an unpinned path as missing; only a speech model a person adds with their own URL downloads unpinned.

On Robust Video Matting: its GPL-3.0 licence is incompatible with shipping the
weights inside formcut's builds, and they are never bundled or redistributed.
What the registry offers is a download of the upstream project's own release
file, fetched at the person's explicit request into their own model folder, with
the licence named on the entry and stored beside the file. The earlier exclusion
row said "excluded" without this distinction; the registry and this page now
state the same rule.

BG2 decision, recorded at v1.58.0: the bundled fallback is U2NetP rather than
the MediaPipe selfie segmenter first recorded as the candidate, because the
selfie model ships as tflite and the engine carries ONNX Runtime, not a tflite
runtime, while U2NetP is 4.6 MB of already-vetted Apache-2.0 ONNX from the same
release the download offers, and it is the model the cutout defaults to. The
bundled copy lives at `backend/app/bundled_models/u2netp.onnx` and the model
folder, when populated, takes precedence.

Candidates recorded but not registered (kept so the reasoning is not lost):
MediaPipe Selfie Segmentation (Apache-2.0, tflite; passed over for the runtime
reason above), MODNet (Apache-2.0), BiRefNet (MIT), MobileSAM (Apache-2.0) and
SlimSAM (Apache-2.0); their hashes stay unrecorded until any of them is
registered, and the gate applies then.

Excluded by policy, recorded so the decision is not revisited by accident:

| Model | Licence | Why excluded |
| --- | --- | --- |
| U2Net full weights from some mirrors | unclear or unstated | provenance not verifiable; the Apache-2.0 rembg release is used instead |
| SAM (original, Meta) | Apache-2.0 code, weights under a separate research licence | weight licence does not permit redistribution here |

The gate's ordering rule stands: no entry in the model manager without a hash
in the registry table above, taken from a real fetch of the file and enforced
at download time through the manager's `PINNED` table. A candidate's hash is
recorded in the same change that registers it.

Execution providers (BG6, recorded at v1.60.0): every ONNX Runtime session the
engine opens takes one ordering from `model_manager.providers()`, preferring
the platform accelerator where its provider is present and always keeping the
CPU provider as the floor. The standard `onnxruntime` wheel (MIT) carries the
CPU provider everywhere and Core ML on macOS; DirectML on Windows comes from
`onnxruntime-directml` (MIT, bundling Microsoft's DirectML redistributable);
CUDA on Linux comes from `onnxruntime-gpu` (MIT), which links the machine's
own NVIDIA CUDA libraries at run time under their EULA and redistributes none
of them. Each is a straight package swap the person or a platform build makes;
the engine ships none of the accelerator runtimes itself, and Settings under
Local models names the provider actually in use.

## Krea 2 (optional)

Krea 2 Turbo is neither bundled nor distributed with formcut: its weights are fetched from their publishers on
Hugging Face, onto the person's own computer, only when that person installs it from the Krea 2 card in Studio >
Local models. The card shows the licence's terms and links the full agreement and Krea's Acceptable Use Policy;
nothing downloads until the person accepts the agreement. The content filter section 4.2 requires,
Falconsai/nsfw_image_detection, is always installed with Krea 2 and runs on every picture, withholding what it flags;
there is no option to install Krea 2 without it. If the person later removes it (deleting its files, or changing
their own build), Krea 2 keeps running, the card shows a warning that the filter was knowingly removed and that the
responsibility is the person's alone, and each picture made without it carries that warning; the acknowledgement and
the runs without the filter are recorded in models/krea-2-consent.json. A prompt sexualising minors is refused either
way. The attribution notice of section 3.1(c) is written to models/krea-2/NOTICE.txt and returned with every picture.
Commercial use under the agreement is limited to those with less than $1,000,000 of annual revenue (section 2.3);
formcut shows this, and each person is responsible for their own standing under it. See USE_POLICY.md.
