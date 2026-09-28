# Open-weight models

Everything formcut can run locally, where each model comes from, what licence it
carries, and the code that loads it. Nothing is fetched unless a person asks for
it: every download is triggered from the interface or from the API below, and
the engine ships exactly one small model inside its build, the 4.6 MB U2NetP at
`backend/app/bundled_models/u2netp.onnx`, so the default cutout works before
anything has been downloaded (BG2; the decision is recorded in
[Licences](Licences)). A file in the person's model folder always takes
precedence over the bundled copy.

All of these run through **ONNX Runtime** on the engine side, Whisper included
since v1.62.0 (`backend/app/transcribe.py`); a browser whose engine has no ONNX
Runtime still runs Whisper in the page through **transformers.js**. Both are already
dependencies; no additional runtime is needed for any model in this list. Every
engine-side session takes one provider ordering from
`model_manager.providers()`: the platform accelerator first where present
(Core ML on macOS, DirectML on Windows, CUDA on Linux with NVIDIA), the CPU
provider always the floor; `GET /api/models/runtime` reports what is active,
and Local models shows it as "Processor".

---

## 1. Segmentation and cutout

Used by: **Cutout and brushes** in the Creator panel, **Select subject**
(auto-masking), and background removal. Registered in
`backend/app/model_manager.py`:

| Registry id | Model | Purpose | Licence | Size |
| --- | --- | --- | --- | --- |
| `object-cutout` | `u2netp.onnx` | general object cutout, the small U²-Net; also the bundled out-of-the-box model | Apache-2.0 | ~4.6 MB |
| `person-cutout` | `u2net_human_seg.onnx` | people, trained for human segmentation | Apache-2.0 | ~176 MB |
| `sharp-cutout` | `isnet-general-use.onnx` | IS-Net, sharper edges than U²-Net | Apache-2.0 | ~179 MB |
| `video-matting` | `rvm_mobilenetv3_fp32.onnx` | Robust Video Matting for people in motion; GPL-3.0-only, offered as an explicit download of upstream's own release, never bundled (see [Licences](Licences)) | GPL-3.0-only | ~15 MB |
| `click-select` | SAM 2 Hiera Tiny encoder and decoder | point or box prompts: click what you mean | Apache-2.0 | ~155 MB |
| `click-track` | SAM 2.1 Tiny video (six files) | follows a prompted subject through a clip | Apache-2.0 | ~190 MB |

The model select also offers **Subject (Auto)**, which is an arbitration rather
than a model: the person model runs first, its matte is kept when it holds at
least one percent of the frame at half threshold, and the object model answers
otherwise. Auto needs both models it chooses between, so it is refusable with
the same download message until `person-cutout` is fetched.

The **smart brush** (Smart restore and Smart erase beside the plain pair) turns
a stroke into a prompt: `/api/render/smart-brush` maps the painted points into
the clip's own pixels, spaces up to five of them as positive SAM 2 point
prompts on the frame the stroke was made on, and stores the returned region as
an outline on the stroke, which the matte shaper fills on every frame. Smart
strokes need `click-select` downloaded.

Upstream research: U²-Net, Qin et al., Apache-2.0
(`https://github.com/xuebinqin/U-2-Net`); IS-Net from DIS
(`https://github.com/xuebinqin/DIS`); the ONNX exports are redistributed by the
rembg project (`https://github.com/danielgatis/rembg`, MIT). SAM 2 and 2.1 are
Meta's, Apache-2.0, as ONNX exports; Robust Video Matting is PeterL1n's own
release.

**Adding another model** needs a registry entry with its pin in the same
change (the licence gate in [Licences](Licences)), and an entry in the cutout
allow lists:

```python
# backend/app/model_manager.py
MODELS["birefnet"] = {
    "name": "BiRefNet general matting",
    "license": "MIT",
    "files": {"birefnet-general.onnx":
              "https://github.com/danielgatis/rembg/releases/download/v0.0.0/birefnet-general.onnx"},
}
PINNED["birefnet-general.onnx"] = "<sha256 of the file you fetched>"
```

Then add it to `CUTOUT_MODELS` in `backend/app/segmentation.py` with a branch
in `_infer`, and to the cutout model list in `backend/app/validation.py`.
BiRefNet (MIT) and silueta (Apache-2.0, U²-Net quality at a quarter the size)
remain the recorded candidates, in the same rembg releases.

**The loading code** is `_session` in `backend/app/segmentation.py`; every
session takes the shared provider ordering:

```python
session = onnxruntime.InferenceSession(str(model_file(file)), providers=providers())
# U²-Net family: NCHW float32, 320x320, normalised; one output, the matte
matte = session.run(None, {session.get_inputs()[0].name: tensor})[0][0][0]
```

`model_file()` answers model-folder-first, then the bundle. `outline()` in the
same module traces a matte into editable mask anchors, which is what **Select
subject** returns, and what a smart stroke's region is stored as.

**Absent-model behaviour:** `object-cutout` is always ready through the bundle,
so the default cutout mattes out of the box; any other choice refuses with a
download message until fetched, and the renderer reads a cached matte and
renders the clip unmatted when there is none, rather than stalling.

---

## 2. Speech synthesis

Used by: **Studio → Local speech**. Registered as `local-speech` (Kokoro);
Pocket TTS (Kyutai, CC-BY-4.0 weights) and Chatterbox (Resemble AI, MIT, with
an inaudible watermark on its audio) are installable engines beside it, set up
once with `backend/setup_local_ai.py` and chosen from the same panel.

| File | Licence | Size |
| --- | --- | --- |
| `kokoro-v1.0.onnx` | Apache-2.0 | ~310 MB |
| `voices-v1.0.bin` | Apache-2.0 | ~27 MB |

**Links**

- `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx`
- `https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin`

Upstream weights: `https://huggingface.co/hexgrad/Kokoro-82M` (Apache-2.0).
Runtime wrapper: `https://github.com/thewh1teagle/kokoro-onnx` (MIT).

**Adding other voice models** needs no code: the engine takes them at runtime.

```
POST /api/models/speech
{"id": "piper-en", "name": "Piper English",
 "model_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
 "voices_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
 "license": "MIT"}
```

Piper voices (`https://github.com/rhasspy/piper`, MIT) are the usual alternative:
around 60 MB each, many languages, listed at
`https://huggingface.co/rhasspy/piper-voices`.

---

## 3. Transcription and captions

Used by: **Captions**. Since v1.62.0 these run **in the engine** through ONNX
Runtime with the shared provider ordering (`backend/app/transcribe.py`, the job
behind `POST /api/transcribe`), word times taken from the model's alignment
heads; a browser whose engine answers 503 runs the first six in the page through
transformers.js instead. All are fetched from the Hugging Face hub on first use.
The allowlist is `WHISPER_MODELS` plus `ENGINE_WHISPER_MODELS` in
`backend/app/model_manager.py`; the last three are the engine's alone and are
never prefetched by `FORMCUT_MODELS_AUTO=all`.

| Model | Licence | Size (quantised) |
| --- | --- | --- |
| `Xenova/whisper-tiny.en` | MIT | ~40 MB |
| `Xenova/whisper-base.en` | MIT | ~80 MB |
| `Xenova/whisper-small.en` | MIT | ~250 MB |
| `onnx-community/whisper-tiny` | MIT | ~40 MB |
| `onnx-community/whisper-base` | MIT | ~80 MB |
| `onnx-community/whisper-small` | MIT | ~250 MB |
| `Xenova/whisper-medium.en` (engine only) | MIT | ~776 MB |
| `Xenova/whisper-medium` (engine only) | MIT | ~776 MB |
| `onnx-community/whisper-large-v3-turbo` (engine only, multilingual) | MIT | ~1.08 GB |

Weights are OpenAI Whisper (MIT, `https://github.com/openai/whisper`); the
repositories above are ONNX conversions. The `.en` variants are English-only and
noticeably better at English than the multilingual model of the same size.

Loading code is in the captions worker:

```ts
import { pipeline } from "@huggingface/transformers";
const transcribe = await pipeline("automatic-speech-recognition", modelId, {
  device: navigator.gpu ? "webgpu" : "wasm",
});
```

---

## 4. Upscaling

Used by: **AI upscale**. Registered as `ai-upscale`: Real-ESRGAN x4plus as an
ONNX export (`realesrgan-x4plus.onnx`, BSD-3-Clause, ~67 MB), converted from
the official weights by a published, reproducible recipe and pinned to the
converter's stated SHA-256. The upscaler tiles the frame and runs through the
same provider ordering as everything else.

---

## 5. Not yet wired, but the obvious next additions

These have no code in formcut today. Each needs a registry entry with its pin,
a place in the interface, and a call site; the links are here so that work does
not start with a search.

| Purpose | Model | Licence | Link |
| --- | --- | --- | --- |
| Interpolation | RIFE v4.6 ONNX | MIT | `https://github.com/hzwer/Practical-RIFE` |
| Depth, for 3D effects | Depth Anything V2 Small | Apache-2.0 | `https://huggingface.co/depth-anything/Depth-Anything-V2-Small` |
| Face detection | YuNet ONNX | Apache-2.0 | `https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet` |
| Speech separation | Demucs v4 | MIT | `https://github.com/facebookresearch/demucs` |
| Denoise, audio | DeepFilterNet 3 | Apache-2.0 / MIT | `https://github.com/Rikorose/DeepFilterNet` |
| Upscaling, animation | RealESRGAN-x4plus-anime | BSD-3-Clause | Real-ESRGAN releases |

The earlier entries on this list have landed: Real-ESRGAN is `ai-upscale`,
SAM 2 is `click-select` and `click-track`, and Pocket TTS and Chatterbox are
installable speech engines.

---

## How downloads work

Every model is fetched by the same path, so nothing above needs special code:

```
GET    /api/models                  what is registered and what is on disk
GET    /api/models/runtime          the active execution provider and the available list
POST   /api/models/{id}/download    fetch it, as a job with progress
POST   /api/models/{id}/import      supply a file you already have
DELETE /api/models/{id}             remove it
GET    /api/models/speech           speech models added at runtime
POST   /api/models/speech           add one
```

Three things are true of all of them:

- **Nothing is fetched without being asked.** The one weight the engine
  carries is the bundled U2NetP, inside the build itself, so the default
  cutout works offline from the first run. `FORMCUT_MODELS_AUTO` governs
  startup fetching: `1` (the default) fetches only the default cutout model
  into the model folder, `all` fetches every permissively licensed model for a
  machine that will go offline, `0` fetches nothing.
- **Checksums are pinned.** `PINNED` in `model_manager.py` holds a SHA-256 for
  every registry file, taken from real fetches and matching the table in
  [Licences](Licences); a mismatch deletes the download rather than caching it.
  Add a pin in the same change that adds a model.
- **Sources are redirectable.** `sources.json` in the data directory lets a
  person point any model at a mirror or a local path, for machines that cannot
  reach GitHub or Hugging Face; the pin still applies, so a mirror cannot
  substitute a different file.

## Local image models on Apple silicon: Krea 2, FLUX.2 [klein], LoRA stacks

Krea 2 Turbo and FLUX.2 [klein] 4B and 9B are optional, installed from their cards in Studio > Local models and run
by mflux in their own environment. None of them ships with formcut: their MLX builds come from mflux-community on
Hugging Face, pinned file by file, when you install them. FLUX.2 [klein] 4B is Apache-2.0; 9B is under the FLUX
Non-Commercial License v2.1 (the model for non-commercial use, its pictures usable for any purpose the licence does not
prohibit), and, like Krea 2, installs with the content filter its licence requires.

In the image generator, a model that takes LoRAs shows its stack: add LoRAs from a `.safetensors` file or a Hugging
Face file link, each tagged with the model it was made for (one made for Klein 4B does not load on 9B or on Krea 2),
each with its strength from -2 to 2 and a switch to leave it out. LoRA and LyCORIS LoKr files load; DoRA in the PEFT
layout does not (mflux refuses it). The library lives in `models/loras/`.

Memory: Automatic uses mflux's low-memory mode when the model would take more than about half of this computer's
memory, Low memory always does (slower), Normal never does; MLX's cache is capped at a tenth of the memory, and one
local image model runs at a time. The generator shows the model's own progress (loading, each step, finishing), and
Cancel ends the model's process.

