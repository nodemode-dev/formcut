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

## ffmpeg in a release bundle

formcut is **Apache-2.0** and stays Apache-2.0 in a release, because it runs
ffmpeg as a **separate program** rather than linking against it. The two meet at
a process boundary, and neither licence reaches across it.

The builds shipped are **LGPL-2.1** (`--disable-gpl --disable-nonfree`).
`setup/fetch_ffmpeg.py` will only assemble a bundle from an LGPL build unless
someone passes `--allow-gpl`, which is deliberate: a GPL ffmpeg inside the
bundle would make the distributed whole GPL-3.0, and formcut's own terms would
no longer describe what was shipped.

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
