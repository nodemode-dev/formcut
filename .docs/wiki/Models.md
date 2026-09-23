# Open-weight models

Everything formcut can run locally, where each model comes from, what licence it
carries, and the code that loads it. Nothing here is fetched unless a person
asks for it: the engine ships no weights, and every download is triggered from
the interface or from the API below.

All of these run through **ONNX Runtime** on the engine side, except Whisper,
which runs in the browser through **transformers.js**. Both are already
dependencies; no additional runtime is needed for any model in this list.

---

## 1. Segmentation and cutout

Used by: **Adjust → Cutout**, **Select subject** (auto-masking), and background
removal. Registered in `backend/app/model_manager.py` as `object-cutout` and
`person-cutout`.

| Model | Purpose | Licence | Size |
| --- | --- | --- | --- |
| `u2netp.onnx` | general object cutout, the small U²-Net | Apache-2.0 | ~4.7 MB |
| `u2net_human_seg.onnx` | people, trained for human segmentation | Apache-2.0 | ~176 MB |

**Links**

- `https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx`
- `https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx`

Upstream research: U²-Net, Qin et al., Apache-2.0 —
`https://github.com/xuebinqin/U-2-Net`. The ONNX exports above are redistributed
by the rembg project (`https://github.com/danielgatis/rembg`, MIT), which is the
practical source most tools use.

**Optional, better quality, heavier**

| Model | Purpose | Licence | Link |
| --- | --- | --- | --- |
| `isnet-general-use.onnx` | sharper edges than u2netp | Apache-2.0 | `https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx` |
| `birefnet-general.onnx` | current state of the art for matting | MIT | `https://github.com/danielgatis/rembg/releases/download/v0.0.0/birefnet-general.onnx` |
| `silueta.onnx` | u2net quality at a quarter the size | Apache-2.0 | `https://github.com/danielgatis/rembg/releases/download/v0.0.0/silueta.onnx` |

To add one, no code is needed beyond a registry entry:

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

Then allow it in `backend/app/validation.py`, where cutout models are checked:

```python
if cutout.get('model') not in ('object-cutout', 'person-cutout', 'birefnet'):
    raise ValueError('Unknown cutout model')
```

**The loading code already exists** in `backend/app/segmentation.py`. Its shape:

```python
session = onnxruntime.InferenceSession(path, providers=["CPUExecutionProvider"])
# U²-Net family: NCHW float32, 320x320, normalised; one output, the matte
matte = session.run(None, {session.get_inputs()[0].name: tensor})[0][0][0]
```

`outline()` in that module traces a matte into editable mask anchors, which is
what **Select subject** returns.

**Absent-model behaviour:** the renderer reads a cached matte and renders the
clip unmatted when there is none, rather than stalling. The Adjust panel reports
how many models are missing and offers to fetch them.

---

## 2. Speech synthesis

Used by: **Studio → Local speech**. Registered as `local-speech`.

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

Used by: **Captions**. These run **in the browser**, not the engine, through
transformers.js, and are fetched from the Hugging Face hub on first use. The
allowlist is `WHISPER_MODELS` in `backend/app/model_manager.py`.

| Model | Licence | Size (quantised) |
| --- | --- | --- |
| `Xenova/whisper-tiny.en` | MIT | ~40 MB |
| `Xenova/whisper-base.en` | MIT | ~80 MB |
| `Xenova/whisper-small.en` | MIT | ~250 MB |
| `onnx-community/whisper-tiny` | MIT | ~40 MB |
| `onnx-community/whisper-base` | MIT | ~80 MB |
| `onnx-community/whisper-small` | MIT | ~250 MB |

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

## 4. Not yet wired, but the obvious next additions

These have no code in formcut today. Each needs a registry entry, a place in the
interface, and a call site; the links are here so that work does not start with
a search.

| Purpose | Model | Licence | Link |
| --- | --- | --- | --- |
| Upscaling | Real-ESRGAN x4 ONNX | BSD-3-Clause | `https://github.com/xinntao/Real-ESRGAN` |
| Speech | Pocket TTS (Kyutai) | MIT code, CC-BY-4.0 weights | `https://github.com/kyutai-labs/pocket-tts` |
| Speech | Chatterbox (Resemble AI) | MIT | `https://github.com/resemble-ai/chatterbox` |
| Upscaling, faster | RealESRGAN-x4plus-anime | BSD-3-Clause | same repository, releases |
| Interpolation | RIFE v4.6 ONNX | MIT | `https://github.com/hzwer/Practical-RIFE` |
| Depth, for 3D effects | Depth Anything V2 Small | Apache-2.0 | `https://huggingface.co/depth-anything/Depth-Anything-V2-Small` |
| Face detection | YuNet ONNX | Apache-2.0 | `https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet` |
| Speech separation | Demucs v4 | MIT | `https://github.com/facebookresearch/demucs` |
| Denoise, audio | DeepFilterNet 3 | Apache-2.0 / MIT | `https://github.com/Rikorose/DeepFilterNet` |
| Object tracking | SAM 2 Hiera Tiny | Apache-2.0 | `https://huggingface.co/facebook/sam2-hiera-tiny` |

SAM 2 is the one worth doing first: it would turn **Select subject** from a
whole-frame guess into a click-what-you-mean tool, and it tracks across frames,
which is what a mask on moving footage actually needs.

---

## How downloads work

Every model is fetched by the same path, so nothing above needs special code:

```
GET    /api/models                  what is registered and what is on disk
POST   /api/models/{id}/download    fetch it, as a job with progress
POST   /api/models/{id}/import      supply a file you already have
DELETE /api/models/{id}             remove it
GET    /api/models/speech           speech models added at runtime
POST   /api/models/speech           add one
```

Three things are true of all of them:

- **Nothing is fetched without being asked.** The engine ships no weights and
  downloads none at start.
- **Checksums are pinned.** `PINNED` in `model_manager.py` holds a SHA-256 per
  file; a mismatch deletes the download rather than caching it. Add a pin
  whenever you add a model.
- **Sources are redirectable.** `sources.json` in the data directory lets a
  person point any model at a mirror or a local path, for machines that cannot
  reach GitHub or Hugging Face.
