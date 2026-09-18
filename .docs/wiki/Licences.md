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
| ffmpeg, ffprobe | LGPL or GPL depending on the user-supplied build | External processes on PATH only. Video decoding, probing, audio processing and export use these executables. Distribution builds reject OpenCV wheels with bundled FFmpeg/GStreamer backends; prepare_cv.py builds image processing without them. |

## Icons and assets

All UI icons are hand-authored inline currentColor SVG in this repo, except the timeline and track glyph family in frontend/src/ui/icons-lucide.ts, which is generated from the Lucide set (ISC licence) of the bundled IcoLab library: 22 keys, default style, 24-unit grid, currentColor bodies with stroke weight left to the caller. ISC requires the copyright notice be retained, which travels with the set; no attribution is displayed in the UI and no icon package is a dependency. The brand glyph, favicon, PWA icons and Tauri icon set derive from the owner-supplied formcut icon (src-tauri/icons/formcut-icon.svg). The demo media in examples/demo (input-clip-example.mp4, model-drop-MV.mp4, a-sample.wav, effect-example-image.jpg) were supplied by the project owner for this build; they carry no third-party license grant here, and rights to the portrait, music video and clip must be confirmed by the owner before public distribution. examples/demo is not bundled into frozen builds.

## Implementation dependencies

| Component | License | Distribution decision |
| --- | --- | --- |
| NumPy 2.2.x | BSD-3-Clause; wheel includes its own third-party notices | Engine dependency; preserve distribution metadata |
| Pillow 11.x | HPND; bundled codecs have separate notices | Engine image/text dependency; preserve distribution metadata |
| OpenCV 4.12.0.88 headless | Apache-2.0; upstream wheel codec libraries have additional licenses | Source-build core/imgproc/imgcodecs/features2d/python3 with FFmpeg, GStreamer and GUI backends disabled before freezing |
| wgpu-py 0.31.1 / wgpu-native | BSD-2-Clause / MIT OR Apache-2.0 | GPU composition and custom shaders; preserve package notices |
| ONNX Runtime 1.23.2 | MIT | Local segmentation inference; preserve package notices |
| grpcio | Apache-2.0 | Optional headless transport |
| U2Net / U2NetP weights | Apache-2.0 upstream project | Explicit download into user data; never bundled |
| Kokoro 82M model | Apache-2.0 upstream model card | Explicit download into user data; never bundled |
| kokoro-onnx | MIT wrapper; phonemizer/eSpeak dependencies include GPL terms | External user-installed speech environment only; wrapper, phonemizer and eSpeak excluded from the frozen engine |

Licence sources: [OpenCV packaging](https://github.com/opencv/opencv-python), [Pillow](https://github.com/python-pillow/Pillow), [NumPy](https://github.com/numpy/numpy), [wgpu-py](https://github.com/pygfx/wgpu-py), [wgpu](https://github.com/gfx-rs/wgpu), [ONNX Runtime](https://github.com/microsoft/onnxruntime), [gRPC](https://github.com/grpc/grpc), [U2Net](https://github.com/xuebinqin/U-2-Net), [Kokoro model](https://huggingface.co/hexgrad/Kokoro-82M), [Kokoro ONNX wrapper](https://github.com/thewh1teagle/kokoro-onnx).

The packaging audit found libavcodec/libavformat/libavutil/libswscale in the initial standard OpenCV diagnostic freeze. That output is not a distributable. VideoSource now decodes through external FFmpeg, and freeze.py rejects a codec-enabled OpenCV runtime. Native platform dependency audits remain required on their actual built bundles. No frozen binary or third-party wheel is included in this source release.
