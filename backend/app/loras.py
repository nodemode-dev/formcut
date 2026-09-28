"""The LoRA library for the local image models (Krea 2, FLUX.2 [klein] 4B and 9B).

Each adapter lives in models/loras/<id>/adapter.safetensors with lora.json beside it: its name, the model it was
made for (a LoRA made for Klein 4B does not load on 9B, nor on Krea 2), where it came from, its SHA-256 and size, the
strength it starts at and its trigger words. An adapter is checked before it is kept: a safetensors file whose tensors
are a LoRA (lora_A/lora_B, lora_down/lora_up) or a LyCORIS LoKr (lokr_w1/lokr_w2), which is what mflux loads; a DoRA
in the PEFT layout (a magnitude vector) is refused, as mflux refuses it. A generation names a stack of up to eight,
each with a strength from -2 to 2; resolve() turns it into paths and strengths, refusing one made for another model.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import time
from pathlib import Path

import httpx
from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import jobs
from .model_manager import ROOT

router = APIRouter(prefix="/api/loras", tags=["loras"])

BASES = {"krea-2": "Krea 2", "flux2-klein-4b": "FLUX.2 [klein] 4B", "flux2-klein-9b": "FLUX.2 [klein] 9B"}
LIBRARY = ROOT / "loras"
MAX_BYTES = 3 * 1024**3
MAX_STACK = 8
SCALES = (-2.0, 2.0)
_HF = re.compile(r"^https://huggingface\.co/([\w.-]+/[\w.-]+)/resolve/([\w.-]+)/([\w./ -]+\.safetensors)(\?download=true)?$")


def inspect(path: Path) -> dict:
    """What the file is, from its safetensors header alone; ValueError with the reason when it is not an adapter."""
    with open(path, "rb") as handle:
        head = handle.read(8)
        if len(head) < 8:
            raise ValueError("not a safetensors file")
        (length,) = struct.unpack("<Q", head)
        if not 2 <= length <= 100_000_000:
            raise ValueError("not a safetensors file")
        try:
            header = json.loads(handle.read(length))
        except ValueError as exc:
            raise ValueError("not a safetensors file") from exc
    names = [key for key in header if key != "__metadata__"]
    joined = "\n".join(names)
    if "lora_magnitude_vector" in joined or ("dora_scale" in joined and "lora_A" in joined):
        raise ValueError("a DoRA adapter (PEFT layout), which mflux does not load")
    if re.search(r"lokr_w[12]", joined):
        kind = "LoKr"
    elif re.search(r"lora_(A|B|down|up)\b", joined):
        kind = "LoRA"
    else:
        raise ValueError("no LoRA or LoKr tensors in this file")
    return {"format": kind, "tensors": len(names), "metadata": header.get("__metadata__") or {}}


def _entry(folder: Path) -> dict | None:
    try:
        entry = json.loads((folder / "lora.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return entry if (folder / "adapter.safetensors").is_file() else None


def entries(base: str | None = None) -> list[dict]:
    if not LIBRARY.is_dir():
        return []
    found = (_entry(folder) for folder in sorted(LIBRARY.iterdir()) if folder.is_dir())
    return [e for e in found if e and (base is None or e["base"] == base)]


def add(source_file: Path, name: str, base: str, source: str) -> dict:
    """Check a downloaded or uploaded file and keep it in the library."""
    if base not in BASES:
        raise ValueError(f"choose the model the LoRA was made for: {', '.join(BASES.values())}")
    if source_file.stat().st_size > MAX_BYTES:
        raise ValueError("a LoRA over 3 GB is not taken")
    facts = inspect(source_file)
    digest = hashlib.sha256()
    with open(source_file, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    sha = digest.hexdigest()
    for existing in entries():
        if existing["sha256"] == sha and existing["base"] == base:
            return existing
    clean = re.sub(r"[^\w .()-]", "", name).strip()[:60] or source_file.stem[:60]
    lora_id = f"{re.sub(r'[^a-z0-9]+', '-', clean.lower()).strip('-')[:40] or 'lora'}-{sha[:8]}"
    folder = LIBRARY / lora_id
    folder.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_file), folder / "adapter.safetensors")
    trained = facts["metadata"].get("ss_tag_frequency") or ""
    entry = {
        "id": lora_id,
        "name": clean,
        "base": base,
        "source": source,
        "sha256": sha,
        "bytes": (folder / "adapter.safetensors").stat().st_size,
        "format": facts["format"],
        "scale": 1.0,
        "triggers": str(facts["metadata"].get("trigger_words") or facts["metadata"].get("instance_prompt") or "")[:200],
        "added": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "trained": bool(trained),
    }
    (folder / "lora.json").write_text(json.dumps(entry, indent=1), encoding="utf-8")
    return entry


def resolve(stack: list | None, base: str) -> list[tuple[str, float]]:
    """A generation's stack as (path, strength) pairs, the disabled and zero-strength ones left out."""
    if not stack:
        return []
    if not isinstance(stack, list) or len(stack) > MAX_STACK:
        raise ValueError(f"a stack of up to {MAX_STACK} LoRAs")
    by_id = {entry["id"]: entry for entry in entries()}
    out = []
    for item in stack:
        if not isinstance(item, dict) or item.get("enabled") is False:
            continue
        entry = by_id.get(str(item.get("id")))
        if entry is None:
            raise ValueError(f"no LoRA {item.get('id')!r} in the library")
        if entry["base"] != base:
            raise ValueError(f"{entry['name']} was made for {BASES[entry['base']]}, not {BASES.get(base, base)}")
        scale = max(SCALES[0], min(SCALES[1], float(item.get("scale", entry["scale"]))))
        if scale:
            out.append((str(LIBRARY / entry["id"] / "adapter.safetensors"), round(scale, 3)))
    return out


def mflux_flags(pairs: list[tuple[str, float]]) -> list[str]:
    if not pairs:
        return []
    return ["--lora-paths", *(p for p, _ in pairs), "--lora-scales", *(f"{s:g}" for _, s in pairs)]


@router.get("")
def list_loras(base: str | None = None) -> dict:
    return {"loras": entries(base), "bases": BASES, "maxStack": MAX_STACK, "scales": SCALES}


@router.post("/import")
def import_lora(file: UploadFile, base: str = Form(...), name: str = Form("")) -> dict:
    LIBRARY.mkdir(parents=True, exist_ok=True)
    part = LIBRARY / f".import-{time.time_ns()}.part"
    size = 0
    with open(part, "wb") as handle:
        while block := file.file.read(1 << 20):
            size += len(block)
            if size > MAX_BYTES:
                part.unlink(missing_ok=True)
                raise HTTPException(413, "a LoRA over 3 GB is not taken")
            handle.write(block)
    try:
        return add(part, name or Path(file.filename or "lora").stem, base, f"file: {file.filename}")
    except ValueError as exc:
        part.unlink(missing_ok=True)
        raise HTTPException(400, f"Not added: {exc}") from exc


class FetchBody(BaseModel):
    url: str
    base: str
    name: str = ""


@router.post("/fetch", status_code=202)
def fetch_lora(body: FetchBody) -> dict:
    """A LoRA from Hugging Face by its file link (https://huggingface.co/<repo>/resolve/<revision>/<file>.safetensors)."""
    match = _HF.match(body.url.strip())
    if not match:
        raise HTTPException(400, "Give the file's Hugging Face link: https://huggingface.co/<repo>/resolve/<revision>/<file>.safetensors")
    if body.base not in BASES:
        raise HTTPException(400, "Choose the model the LoRA was made for")
    repo, revision, name = match.group(1), match.group(2), match.group(3)

    def work(_job, report, cancelled):
        LIBRARY.mkdir(parents=True, exist_ok=True)
        part = LIBRARY / f".fetch-{time.time_ns()}.part"
        try:
            with httpx.stream(
                "GET", f"https://huggingface.co/{repo}/resolve/{revision}/{name}", follow_redirects=True, timeout=60
            ) as reply:
                if reply.status_code != 200:
                    raise ValueError(f"Hugging Face answered {reply.status_code} (a gated repository needs its licence accepted there)")
                total = int(reply.headers.get("content-length") or 0)
                if total > MAX_BYTES:
                    raise ValueError("a LoRA over 3 GB is not taken")
                done = 0
                with open(part, "wb") as handle:
                    for block in reply.iter_bytes(1 << 20):
                        if cancelled():
                            raise InterruptedError("cancelled")
                        done += len(block)
                        if done > MAX_BYTES:
                            raise ValueError("a LoRA over 3 GB is not taken")
                        handle.write(block)
                        if total:
                            report(done / total)
            return {"lora": add(part, body.name or Path(name).stem, body.base, f"https://huggingface.co/{repo} ({revision}) {name}")}
        finally:
            part.unlink(missing_ok=True)

    return jobs.submit("lora-fetch", work)


class EditBody(BaseModel):
    name: str | None = None
    base: str | None = None
    scale: float | None = None
    triggers: str | None = None


@router.patch("/{lora_id}")
def edit_lora(lora_id: str, body: EditBody) -> dict:
    folder = LIBRARY / lora_id
    entry = _entry(folder) if re.fullmatch(r"[\w.-]+", lora_id) else None
    if entry is None:
        raise HTTPException(404, "No such LoRA")
    if body.base is not None and body.base not in BASES:
        raise HTTPException(400, "Unknown model")
    for key in ("name", "base", "triggers"):
        if getattr(body, key) is not None:
            entry[key] = str(getattr(body, key))[:200]
    if body.scale is not None:
        entry["scale"] = max(SCALES[0], min(SCALES[1], float(body.scale)))
    (folder / "lora.json").write_text(json.dumps(entry, indent=1), encoding="utf-8")
    return entry


@router.delete("/{lora_id}")
def remove_lora(lora_id: str) -> dict:
    folder = LIBRARY / lora_id
    if not re.fullmatch(r"[\w.-]+", lora_id) or _entry(folder) is None:
        raise HTTPException(404, "No such LoRA")
    shutil.rmtree(folder)
    return {"removed": lora_id}
