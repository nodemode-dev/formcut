import hashlib
import json
import os
import shutil
import threading

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import jobs
from .paths import DATA_DIR, MODELS_DIR

router = APIRouter(prefix="/api/models", tags=["models"])
ROOT = MODELS_DIR
LEGACY = DATA_DIR / "models"
MODELS = {
    "object-cutout": {"name": "Object cutout (U2Net small)", "license": "Apache-2.0", "files": {"u2netp.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"}},
    "person-cutout": {"name": "Person cutout (U2Net)", "license": "Apache-2.0", "files": {"u2net_human_seg.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx"}},
    "local-speech": {"name": "Kokoro local speech", "license": "Apache-2.0", "files": {
        "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx",
        "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin",
    }},
}
_lock = threading.RLock()
_downloading: set[str] = set()


def ready(model: str) -> bool:
    return model in MODELS and all((ROOT / name).is_file() and (ROOT / name).stat().st_size > 1024 for name in MODELS[model]["files"])


@router.get("")
def list_models():
    return [{"id": key, "name": spec["name"], "license": spec["license"], "ready": ready(key), "downloading": key in _downloading, "files": list(spec["files"])} for key, spec in MODELS.items()]


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
            temporary = path.with_suffix(path.suffix + ".download")
            digest = hashlib.sha256()
            try:
                with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
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
                temporary.replace(path)
                path.with_suffix(path.suffix + ".json").write_text(json.dumps({"url": url, "sha256": digest.hexdigest(), "license": MODELS[model]["license"]}))
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


def prepare(report, cancelled, fetch: bool) -> dict:
    adopted = adopt_legacy()
    missing = [model for model in MODELS if not ready(model)] if fetch else []
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
    for model, paths in (HUB_PREFETCH.items() if fetch else ()):
        for path in paths:
            if cancelled():
                raise InterruptedError("Cancelled")
            try:
                hub.append({"file": f"{model}/{path}", "ready": hub_fetch(model, path) is not None})
            except Exception as error:
                hub.append({"file": f"{model}/{path}", "ready": False, "error": str(error)})
    return {"adopted": adopted, "downloads": results, "hub": hub}


def auto_download() -> dict:
    fetch = os.environ.get("FORMCUT_MODELS_AUTO", "1") != "0"
    return jobs.submit("model-setup", lambda _id, report, cancelled: prepare(report, cancelled, fetch))


HUB = ROOT / "hub"
HUB_MODELS = {"Xenova/whisper-tiny.en", "onnx-community/whisper-tiny"}
HUB_PREFETCH = {model: ("config.json", "generation_config.json", "preprocessor_config.json", "tokenizer.json", "tokenizer_config.json", "onnx/encoder_model_quantized.onnx", "onnx/decoder_model_merged_quantized.onnx") for model in ("Xenova/whisper-tiny.en", "onnx-community/whisper-tiny")}
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
