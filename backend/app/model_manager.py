import hashlib
import json
import threading

import httpx
from fastapi import APIRouter, HTTPException, UploadFile

from . import jobs
from .paths import DATA_DIR

router = APIRouter(prefix="/api/models", tags=["models"])
ROOT = DATA_DIR / "models"
MODELS = {
    "object-cutout": {"name": "Object cutout (U2Net small)", "license": "Apache-2.0", "files": {"u2netp.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"}},
    "person-cutout": {"name": "Person cutout (U2Net)", "license": "Apache-2.0", "files": {"u2net_human_seg.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx"}},
    "local-speech": {"name": "Kokoro local speech", "license": "Apache-2.0", "files": {
        "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx",
        "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin",
    }},
}
_lock = threading.RLock()


def ready(model: str) -> bool:
    return model in MODELS and all((ROOT / name).is_file() and (ROOT / name).stat().st_size > 1024 for name in MODELS[model]["files"])


@router.get("")
def list_models():
    return [{"id": key, "name": spec["name"], "license": spec["license"], "ready": ready(key), "files": list(spec["files"])} for key, spec in MODELS.items()]


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


@router.post("/{model}/download", status_code=202)
def start_download(model: str):
    if model not in MODELS:
        raise HTTPException(404, "Unknown model")
    return jobs.submit("model-download", lambda _id, report, cancelled: download(model, report, cancelled))


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
