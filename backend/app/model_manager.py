import hashlib
import json
import os
import shutil
import threading
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import jobs
from .paths import DATA_DIR, MODELS_DIR

router = APIRouter(prefix="/api/models", tags=["models"])
ROOT = MODELS_DIR
LEGACY = DATA_DIR / "models"
# BG2: models shipped inside the engine build, so the default cutout works on
# a machine that has downloaded nothing. A file in the person's model folder
# always takes precedence; the bundle only answers when the folder is empty.
# Resolved the way effect_packages resolves its library: beside this module,
# which under PyInstaller lands at _MEIPASS/app/bundled_models via freeze.py.
BUNDLED = Path(__file__).resolve().parent / "bundled_models"


def model_file(name: str) -> Path:
    """Where a model file actually is: the model folder, else the bundle."""
    path = ROOT / name
    if path.is_file() and path.stat().st_size > 1024:
        return path
    bundled = BUNDLED / name
    if bundled.is_file():
        return bundled
    return path


# BG6: one ordering for every ONNX Runtime session the engine opens. The
# platform accelerator comes first where its provider is present (Core ML on
# macOS in the standard wheel, DirectML on Windows via onnxruntime-directml,
# CUDA on Linux via onnxruntime-gpu), and the CPU provider is always the
# floor, so a machine with nothing extra runs everything unchanged.
PROVIDERS = ("CoreMLExecutionProvider", "DmlExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider")


def providers() -> list[str]:
    """The execution providers to hand a session, best first."""
    import onnxruntime as ort

    available = ort.get_available_providers()
    return [name for name in PROVIDERS if name in available] or ["CPUExecutionProvider"]


MODELS = {
    # Heavier segmentation, offered rather than required: the cutout works
    # without them and is better with them.
    "video-matting": {
        "name": "Robust Video Matting",
        "license": "GPL-3.0-only",
        "note": "not bundled; fetched only if a person asks for it",
        "files": {
            "rvm_mobilenetv3_fp32.onnx": "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx"
        },
    },
    "sharp-cutout": {
        "name": "IS-Net general matting",
        "license": "Apache-2.0",
        "files": {"isnet-general-use.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"},
    },
    "click-select": {
        "name": "SAM 2 Hiera Tiny",
        "license": "Apache-2.0",
        # SAM 2 ships as PyTorch weights; these are the ONNX exports an engine
        # running ONNX Runtime can load. The url here first was a file that does
        # not exist, which is why it returned 404 rather than downloading.
        "files": {
            "sam2_hiera_tiny.encoder.onnx": "https://huggingface.co/vietanhdev/segment-anything-2-onnx-models/resolve/main/sam2_hiera_tiny.encoder.onnx",
            "sam2_hiera_tiny.decoder.onnx": "https://huggingface.co/vietanhdev/segment-anything-2-onnx-models/resolve/main/sam2_hiera_tiny.decoder.onnx",
        },
    },
    "click-track": {
        "name": "SAM 2.1 video tracking",
        "license": "Apache-2.0",
        # SAM 2.1 Hiera Tiny with its memory encoder, memory attention and
        # object pointers, so a point on one frame is followed through a clip.
        "files": {
            f"sam21-video-{name}": f"https://huggingface.co/square-zero-labs/sam2.1-tiny-video-onnx/resolve/main/{path}"
            for name, path in (
                ("vision_encoder.onnx", "onnx/vision_encoder.onnx"),
                ("mask_decoder.onnx", "onnx/mask_decoder.onnx"),
                ("memory_encoder.onnx", "onnx/memory_encoder.onnx"),
                ("memory_attention.onnx", "onnx/memory_attention.onnx"),
                ("pointer_tpos.onnx", "onnx/pointer_tpos.onnx"),
                ("constants.json", "constants.json"),
            )
        },
    },
    "object-cutout": {
        "name": "Object cutout (U2Net small)",
        "license": "Apache-2.0",
        "files": {"u2netp.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"},
    },
    "person-cutout": {
        "name": "Person cutout (U2Net)",
        "license": "Apache-2.0",
        "files": {"u2net_human_seg.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx"},
    },
    "ai-upscale": {
        "name": "Real-ESRGAN x4plus",
        "license": "BSD-3-Clause",
        # Converted to ONNX from the official RealESRGAN_x4plus.pth by a published,
        # reproducible recipe; pinned below to the converter's stated SHA-256.
        "files": {"realesrgan-x4plus.onnx": "https://huggingface.co/skillsafe-ai/realesrgan-x4plus/resolve/main/model.onnx"},
    },
    "local-speech": {
        "name": "Kokoro local speech",
        "license": "Apache-2.0",
        "files": {
            "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx",
            "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin",
        },
    },
}
_lock = threading.RLock()
_downloading: set[str] = set()


def ready(model: str) -> bool:
    return model in MODELS and all(model_file(name).is_file() and model_file(name).stat().st_size > 1024 for name in MODELS[model]["files"])


@router.get("/runtime")
def runtime():
    """BG6: what this machine offers and which provider sessions will use."""
    import onnxruntime as ort

    chosen = providers()
    return {"active": chosen[0], "available": ort.get_available_providers()}


@router.get("")
def list_models():
    return [
        {
            "id": key,
            "name": spec["name"],
            "license": spec["license"],
            "ready": ready(key),
            "downloading": key in _downloading,
            "files": list(spec["files"]),
        }
        for key, spec in MODELS.items()
    ]


def download(model: str, report, cancelled):
    if model not in MODELS:
        raise ValueError("Unknown model")
    ROOT.mkdir(parents=True, exist_ok=True)
    with _lock:
        entries = list(MODELS[model]["files"].items())
        for i, (name, url) in enumerate(entries):
            path = ROOT / name
            if path.is_file():
                continue
            # A per-model source may override the declared one; keeping it in a
            # separate name makes clear the loop's value is not being rewritten.
            download_url = source_for(model, name, url)
            temporary = path.with_suffix(path.suffix + ".download")
            digest = hashlib.sha256()
            try:
                with httpx.stream("GET", download_url, follow_redirects=True, timeout=120) as response:
                    response.raise_for_status()
                    length = int(response.headers.get("content-length", 0))
                    written = 0
                    with temporary.open("wb") as out:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if cancelled():
                                raise InterruptedError("Cancelled")
                            written += len(chunk)
                            if written > 2_000_000_000:
                                raise ValueError("Model exceeds the download limit")
                            out.write(chunk)
                            digest.update(chunk)
                            report((i + (written / length if length else 0.5)) / len(entries))
                if temporary.stat().st_size < 1024:
                    raise ValueError("Model download is incomplete")
                expected = PINNED.get(name)
                if expected and digest.hexdigest() != expected:
                    # P8: a file that does not match its pin never lands. It is
                    # deleted and named, so a bad mirror cannot poison the cache.
                    temporary.unlink(missing_ok=True)
                    raise ValueError(f"Checksum mismatch for {name}: expected {expected[:16]}..., got {digest.hexdigest()[:16]}...")
                temporary.replace(path)
                path.with_suffix(path.suffix + ".json").write_text(
                    json.dumps({"url": download_url, "sha256": digest.hexdigest(), "license": MODELS[model]["license"]})
                )
            finally:
                temporary.unlink(missing_ok=True)
    return {"model": model, "ready": ready(model)}


def _tracked(model: str, report, cancelled):
    _downloading.add(model)
    try:
        return download(model, report, cancelled)
    finally:
        _downloading.discard(model)


@router.post("/{model}/download", status_code=202)
def start_download(model: str):
    if model not in MODELS:
        raise HTTPException(404, "Unknown model")
    return jobs.submit("model-download", lambda _id, report, cancelled: _tracked(model, report, cancelled))


def adopt_legacy() -> list[str]:
    moved: list[str] = []
    if not LEGACY.is_dir() or LEGACY.resolve() == ROOT.resolve():
        return moved
    ROOT.mkdir(parents=True, exist_ok=True)
    for spec in MODELS.values():
        for name in spec["files"]:
            for candidate in (name, name + ".json"):
                source, target = LEGACY / candidate, ROOT / candidate
                if source.is_file() and not target.exists():
                    shutil.move(str(source), str(target))
                    moved.append(candidate)
    return moved


# What first launch fetches: the Creator panel's default cutout, a few megabytes.
# Everything else downloads when it is first used, from the button beside it,
# or for Whisper through the hub route the moment the transcriber asks.
FIRST_LAUNCH = ("object-cutout",)


def prepare(report, cancelled, fetch: bool, everything: bool = False) -> dict:
    """Fetch the first-launch models; with everything, every permissively licensed model and the Whisper files."""
    adopted = adopt_legacy()
    wanted = [model for model in MODELS if "GPL" not in MODELS[model]["license"]] if everything else list(FIRST_LAUNCH)
    missing = [model for model in wanted if not ready(model)] if fetch else []
    results = []
    for i, model in enumerate(missing):
        if cancelled():
            raise InterruptedError("Cancelled")
        try:
            results.append(_tracked(model, lambda fraction, i=i: report((i + fraction) / len(missing)), cancelled))
        except InterruptedError:
            raise
        except Exception as error:
            results.append({"model": model, "ready": False, "error": str(error)})
    hub = []
    for model, paths in HUB_PREFETCH.items() if fetch and everything else ():
        for path in paths:
            if cancelled():
                raise InterruptedError("Cancelled")
            try:
                hub.append({"file": f"{model}/{path}", "ready": hub_fetch(model, path) is not None})
            except Exception as error:
                hub.append({"file": f"{model}/{path}", "ready": False, "error": str(error)})
    return {"adopted": adopted, "downloads": results, "hub": hub}


def auto_download() -> dict:
    mode = os.environ.get("FORMCUT_MODELS_AUTO", "1")
    return jobs.submit("model-setup", lambda _id, report, cancelled: prepare(report, cancelled, mode != "0", mode == "all"))


HUB = ROOT / "hub"
# C1 offers tiny, base and small in English-only and multilingual form, so every
# one of those must be allowed through the hub or the worker's request is refused.
WHISPER_MODELS = (
    "Xenova/whisper-tiny.en",
    "Xenova/whisper-base.en",
    "Xenova/whisper-small.en",
    "onnx-community/whisper-tiny",
    "onnx-community/whisper-base",
    "onnx-community/whisper-small",
)
HUB_MODELS = set(WHISPER_MODELS)
# The engine's own transcriber (transcribe.py) also runs medium and large,
# which no webview holds; allowed through the hub, never prefetched (1.8 GB).
ENGINE_WHISPER_MODELS = ("Xenova/whisper-medium.en", "Xenova/whisper-medium", "onnx-community/whisper-large-v3-turbo")
HUB_MODELS.update(ENGINE_WHISPER_MODELS)
HUB_PREFETCH = {
    model: (
        "config.json",
        "generation_config.json",
        "preprocessor_config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "onnx/encoder_model_quantized.onnx",
        "onnx/decoder_model_merged_quantized.onnx",
    )
    for model in WHISPER_MODELS
}
_hub_lock = threading.Lock()


def hub_fetch(model: str, path: str):
    parts = path.split("/")
    if model not in HUB_MODELS or any(part in ("", ".", "..") or "\\" in part for part in parts):
        return None
    target = HUB.joinpath(*model.split("/"), *parts)
    with _hub_lock:
        if target.is_file():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".download")
        try:
            with httpx.stream("GET", f"https://huggingface.co/{model}/resolve/main/{path}", follow_redirects=True, timeout=120) as response:
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                written = 0
                with temporary.open("wb") as out:
                    for chunk in response.iter_bytes(1024 * 1024):
                        written += len(chunk)
                        if written > 1_000_000_000:
                            raise ValueError("Model file exceeds the download limit")
                        out.write(chunk)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


@router.get("/hub/{owner}/{name}/resolve/{revision}/{path:path}")
def hub_file(owner: str, name: str, revision: str, path: str):
    target = hub_fetch(f"{owner}/{name}", path) if revision == "main" else None
    if target is None:
        raise HTTPException(404, "No such model file")
    return FileResponse(target)


@router.post("/{model}/import", status_code=201)
def import_model(model: str, file: UploadFile):
    if model not in MODELS or file.filename not in MODELS[model]["files"]:
        raise HTTPException(422, "Choose a model file with the expected filename")
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / file.filename
    temporary = target.with_suffix(target.suffix + ".upload")
    count = 0
    try:
        with temporary.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                count += len(chunk)
                if count > 2_000_000_000:
                    raise HTTPException(413, "Model is too large")
                out.write(chunk)
        if count < 1024:
            raise HTTPException(422, "Model file is incomplete")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {"model": model, "ready": ready(model)}


# P8: pinned SHA-256 per file. A name absent here is unpinned and recorded on
# first download instead, so a pin can be added from a verified machine later.
PINNED: dict[str, str] = {
    # BG1's gate, completed at v1.58.0: every registry file pinned to the
    # SHA-256 of the file actually fetched and hashed, matching the table in
    # .docs/wiki/Licences.md. A download that does not match never lands.
    "rvm_mobilenetv3_fp32.onnx": "88d4531297118f595bf2fd60f6f566aec2e559393802d1f436c380f0cbbd2828",
    "isnet-general-use.onnx": "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a",
    "sam2_hiera_tiny.encoder.onnx": "4cc015ee18520e93f8c7ddfeaca7436039daaaaf19721b4b96a8810a805e82f7",
    "sam2_hiera_tiny.decoder.onnx": "f5a4bd656c143899fb7f52d64ed81e6f6aeb37d477a0b6da50146ac7cf2187bf",
    "sam21-video-vision_encoder.onnx": "aa7a8542942f042e235a993a1ab0ccf5f049918500577802a7f10ec1b39bb873",
    "sam21-video-mask_decoder.onnx": "0461896de3db00936fe1643506f129d71cb6d5d2ae15754811756b7ea1b070c6",
    "sam21-video-memory_encoder.onnx": "580d246c109de88838f600ba7c1c0d03d1fe267f7641b06f8c88c5f0dc5834cd",
    "sam21-video-memory_attention.onnx": "791e648ce8f5ef91ad00ba06e83066ff261ae5a645f0b042b4f46a89fd054baf",
    "sam21-video-pointer_tpos.onnx": "7e71df1d75dba09bc18dd4ae745c2a2cceebdd14d84eadea2fe65d0205f101fc",
    "sam21-video-constants.json": "172edc70e892aab0aef6caedf97b8e4091fbf6c5d26dac5fd9ea69d093d927d3",
    "u2netp.onnx": "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8",
    "u2net_human_seg.onnx": "01eb6a29a5c4d8edb30b56adad9bb3a2a0535338e480724a213e0acfd2d1c73c",
    "realesrgan-x4plus.onnx": "4851ec156207d271f5328605d0582eeb851e656227da8aca093ced9e60789291",
    "kokoro-v1.0.onnx": "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}

SOURCES_FILE = ROOT / "sources.json"


def _sources() -> dict:
    if SOURCES_FILE.is_file():
        try:
            return json.loads(SOURCES_FILE.read_text())
        except ValueError:
            return {}
    return {}


def source_for(model: str, name: str, default: str) -> str:
    """The URL to fetch a model file from: upstream, a mirror, or a custom URL."""
    chosen = _sources().get(model) or {}
    if isinstance(chosen, dict):
        if chosen.get("mode") == "custom" and chosen.get("url"):
            # A custom source is the exact URL the user gave; only a mirror is
            # treated as a base that the file name is appended to.
            return str(chosen["url"])
        if chosen.get("mode") == "mirror" and chosen.get("url"):
            return f"{str(chosen['url']).rstrip('/')}/{name}"
    return default


def set_source(model: str, mode: str, url: str | None) -> dict:
    """Record where a model should be fetched from."""
    if model not in MODELS:
        raise ValueError("Unknown model")
    if mode not in ("upstream", "mirror", "custom"):
        raise ValueError("Unknown source mode")
    if mode != "upstream" and not url:
        raise ValueError("A mirror or custom source needs a URL")
    ROOT.mkdir(parents=True, exist_ok=True)
    data = _sources()
    data[model] = {"mode": mode, "url": url}
    SOURCES_FILE.write_text(json.dumps(data, indent=2))
    return data[model]


def pin_for(name: str) -> str | None:
    return PINNED.get(name)


# Local speech is not one model. A person may add another ONNX voice model and
# its voices file, which is registered beside Kokoro and listed like it; the
# entry lives in the data directory so it survives an update of the app.
SPEECH_FILE = ROOT / "speech-models.json"


class SpeechModelInput(BaseModel):
    id: str = Field(min_length=2, max_length=48, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=80)
    model_url: str = Field(min_length=8, max_length=2000)
    voices_url: str | None = None
    license: str = "unknown"


def _speech_extra() -> dict:
    if SPEECH_FILE.is_file():
        try:
            return json.loads(SPEECH_FILE.read_text())
        except ValueError:
            return {}
    return {}


def load_speech_models() -> None:
    """Merge any added speech models into the registry at start."""
    for key, entry in _speech_extra().items():
        MODELS.setdefault(key, entry)


@router.get("/speech")
def list_speech_models() -> dict:
    return {"models": [{"id": key, **entry} for key, entry in _speech_extra().items()], "builtIn": "local-speech"}


@router.post("/speech", status_code=201)
def add_speech_model(body: SpeechModelInput) -> dict:
    key = f"speech-{body.id}"
    if key in MODELS and key not in _speech_extra():
        raise HTTPException(409, "That id is already used by a built-in model")
    files = {f"{body.id}.onnx": body.model_url}
    if body.voices_url:
        files[f"{body.id}-voices.bin"] = body.voices_url
    entry = {"name": body.name, "license": body.license, "files": files, "kind": "speech", "added": True}
    ROOT.mkdir(parents=True, exist_ok=True)
    data = _speech_extra()
    data[key] = entry
    SPEECH_FILE.write_text(json.dumps(data, indent=2))
    MODELS[key] = entry
    return {"id": key, **entry}


@router.delete("/speech/{key}", status_code=204)
def remove_speech_model(key: str) -> None:
    data = _speech_extra()
    if key not in data:
        raise HTTPException(404, "Unknown speech model")
    for name in data[key].get("files", {}):
        (ROOT / name).unlink(missing_ok=True)
        (ROOT / (name + ".json")).unlink(missing_ok=True)
    data.pop(key)
    SPEECH_FILE.write_text(json.dumps(data, indent=2))
    MODELS.pop(key, None)


load_speech_models()
