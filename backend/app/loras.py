"""The LoRA library for the local image models (Krea 2, FLUX.2 [klein] 4B).

A LoRA is a file in the folder of the model it was made for: models/loras/krea-2/*.safetensors and
models/loras/flux2-klein-4b/*.safetensors. Dropping a file there is all it takes; the Captions-free way in, as the
owner asked. Beside a file, <name>.json may keep what formcut knows of it: its name, where it came from, its SHA-256,
the strength it starts at, its trigger words. Import (a file from this computer) and Add from a link (a Hugging Face
file link, or a Civitai model, version or download link) put the file in the same folder and write that record.

Every file is checked from its safetensors header before it is offered: a LoRA (lora_A/lora_B, lora_down/lora_up) or
a LyCORIS LoKr (lokr_w1/lokr_w2) is what mflux loads; a DoRA in the PEFT layout is refused, as mflux refuses it; a
file that fails is listed with its reason and cannot be stacked. A generation names a stack of up to eight, each with
a strength from -2 to 2; resolve() turns it into paths and strengths, and refuses one made for another model.

A Civitai link names its base model, so the folder is chosen from it: "Krea 2" goes to krea-2, "Flux.2 Klein 4B" (and
its -base) to flux2-klein-4b; any other (Klein 9B, SDXL, Flux.1 ...) is refused, as it would not load. Civitai's own
SHA-256 is checked against the download. Some Civitai files need an account: a Civitai key set in Settings is used.
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

BASES = {"krea-2": "Krea 2", "flux2-klein-4b": "FLUX.2 [klein] 4B"}
CIVITAI_BASES = {"krea 2": "krea-2", "flux.2 klein 4b": "flux2-klein-4b", "flux.2 klein 4b-base": "flux2-klein-4b"}
_CIVITAI = re.compile(
    r"^https://civitai\.(?:com|green)/(?:api/download/models/(\d+)|models/(\d+)(?:/[^?#]*)?(?:\?(?:.*&)?modelVersionId=(\d+))?)"
)
_CHECKED: dict = {}
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


def _migrate() -> None:
    """v2.0.7 kept each LoRA in models/loras/<id>/adapter.safetensors; it moves into its model's folder."""
    if not LIBRARY.is_dir():
        return
    for folder in LIBRARY.iterdir():
        record = folder / "lora.json"
        if folder.name in BASES or not record.is_file():
            continue
        try:
            entry = json.loads(record.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if entry.get("base") in BASES and (folder / "adapter.safetensors").is_file():
            target = LIBRARY / entry["base"]
            target.mkdir(parents=True, exist_ok=True)
            shutil.move(str(folder / "adapter.safetensors"), target / f"{folder.name}.safetensors")
            (target / f"{folder.name}.json").write_text(
                json.dumps({k: v for k, v in entry.items() if k not in ("id", "base")}, indent=1), encoding="utf-8"
            )
            shutil.rmtree(folder, ignore_errors=True)


def _checked(path: Path) -> dict:
    """The header check, remembered while the file is unchanged."""
    stat = path.stat()
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key not in _CHECKED:
        try:
            _CHECKED[key] = {"ok": True, **inspect(path)}
        except (ValueError, OSError) as exc:
            _CHECKED[key] = {"ok": False, "problem": str(exc)}
    return _CHECKED[key]


def _record(path: Path) -> dict:
    try:
        return json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def entries(base: str | None = None) -> list[dict]:
    """Every file in the models' LoRA folders, the dropped ones with the added, each with its check."""
    _migrate()
    out = []
    for key in BASES if base is None else [base] if base in BASES else []:
        folder = LIBRARY / key
        folder.mkdir(parents=True, exist_ok=True)  # the folder is there to drop into
        for path in sorted(folder.glob("*.safetensors")):
            record, check = _record(path), _checked(path)
            out.append(
                {
                    "id": f"{key}/{path.stem}",
                    "name": record.get("name") or path.stem,
                    "base": key,
                    "file": path.name,
                    "bytes": path.stat().st_size,
                    "format": check.get("format"),
                    "usable": check["ok"],
                    "problem": check.get("problem"),
                    "scale": record.get("scale", 1.0),
                    "triggers": record.get("triggers") or str(check.get("metadata", {}).get("trigger_words") or "")[:200],
                    "source": record.get("source") or "dropped into the folder",
                    "sha256": record.get("sha256"),
                    "originalFile": record.get("originalFile"),
                }
            )
    return out


def add(source_file: Path, name: str, base: str, source: str, extra: dict | None = None) -> dict:
    """Check a downloaded or uploaded file and keep it in its model's folder, with its record."""
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
    if extra and extra.get("expectSha256") and extra["expectSha256"].lower() != sha:
        raise ValueError("the download does not match the SHA-256 its source gives")
    for existing in entries(base):
        if existing.get("sha256") == sha:
            source_file.unlink(missing_ok=True)
            return existing
    clean = re.sub(r"[^\w .()-]", "", name).strip()[:60] or source_file.stem[:60]
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", clean).strip("-.")[:60] or "lora"
    folder = LIBRARY / base
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{stem}.safetensors"
    if target.exists():
        target = folder / f"{stem}-{sha[:8]}.safetensors"
    shutil.move(str(source_file), target)
    record = {
        "name": clean,
        "source": source,
        "sha256": sha,
        "scale": 1.0,
        "triggers": (
            (extra or {}).get("triggers") or str(facts["metadata"].get("trigger_words") or facts["metadata"].get("instance_prompt") or "")
        )[:200],
        "added": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "originalFile": (extra or {}).get("originalFile"),  # the name a <lora:name> tag may use
    }
    target.with_suffix(".json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return next(e for e in entries(base) if e["file"] == target.name)


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
        if not entry["usable"]:
            raise ValueError(f"{entry['name']} cannot be used: {entry['problem']}")
        scale = max(SCALES[0], min(SCALES[1], float(item.get("scale", entry["scale"]))))
        if scale:
            out.append((str(LIBRARY / entry["base"] / entry["file"]), round(scale, 3)))
    return out


def mflux_flags(pairs: list[tuple[str, float]]) -> list[str]:
    if not pairs:
        return []
    return ["--lora-paths", *(p for p, _ in pairs), "--lora-scales", *(f"{s:g}" for _, s in pairs)]


def civitai_version(url: str) -> dict:
    """What a Civitai link points to: the version's file (a SafeTensor model file), its SHA-256, trigger words, base
    model and name, from Civitai's public API."""
    from .providers import key_for

    match = _CIVITAI.match(url.strip())
    if not match:
        raise ValueError("give a Civitai model, version or download link")
    headers = {"Authorization": f"Bearer {key_for('civitai')}"} if key_for("civitai") else {}
    version_id = match.group(1) or match.group(3)
    if not version_id:
        model = httpx.get(f"https://civitai.com/api/v1/models/{match.group(2)}", headers=headers, timeout=30).json()
        versions = model.get("modelVersions") or []
        if not versions:
            raise ValueError("that Civitai model has no version to download")
        version_id = str(versions[0]["id"])
    reply = httpx.get(f"https://civitai.com/api/v1/model-versions/{version_id}", headers=headers, timeout=30)
    if reply.status_code != 200:
        raise ValueError(f"Civitai answered {reply.status_code} for version {version_id}")
    version = reply.json()
    files = [
        f
        for f in version.get("files") or []
        if (f.get("metadata") or {}).get("format") == "SafeTensor" and f.get("type") in ("Model", None)
    ]
    if not files:
        raise ValueError("that Civitai version has no .safetensors model file")
    chosen = next((f for f in files if f.get("primary")), files[0])
    civitai_base = str(version.get("baseModel") or "")
    base = CIVITAI_BASES.get(civitai_base.strip().lower())
    return {
        "versionId": version_id,
        "name": (version.get("model") or {}).get("name") or chosen.get("name", "lora"),
        "file": chosen.get("name") or f"{version_id}.safetensors",
        "bytes": int(float(chosen.get("sizeKB") or 0) * 1024),
        "download": chosen.get("downloadUrl") or f"https://civitai.com/api/download/models/{version_id}",
        "sha256": (chosen.get("hashes") or {}).get("SHA256"),
        "triggers": ", ".join(version.get("trainedWords") or []),
        "civitaiBase": civitai_base,
        "base": base,
        "headers": headers,
    }


@router.get("")
def list_loras(base: str | None = None) -> dict:
    return {
        "loras": entries(base),
        "bases": BASES,
        "folders": {key: str(LIBRARY / key) for key in BASES},
        "maxStack": MAX_STACK,
        "scales": SCALES,
    }


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
        return add(part, name or Path(file.filename or "lora").stem, base, f"file: {file.filename}", {"originalFile": file.filename})
    except ValueError as exc:
        part.unlink(missing_ok=True)
        raise HTTPException(400, f"Not added: {exc}") from exc


class FetchBody(BaseModel):
    url: str
    base: str | None = None
    name: str = ""


def _download(url: str, part: Path, headers: dict, report, cancelled) -> None:
    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60) as reply:
        if reply.status_code in (401, 403) and "civitai." in url:
            raise ValueError(
                "Civitai asks for an account to download this file: add your Civitai API key in Settings "
                "(civitai.com, Account settings, API Keys)" + (" (the key given was refused)" if headers else "")
            )
        if reply.status_code in (401, 403):
            raise ValueError(f"Hugging Face answered {reply.status_code}: a gated repository needs its licence accepted there")
        if reply.status_code != 200:
            raise ValueError(f"the source answered {reply.status_code}")
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


@router.post("/fetch", status_code=202)
def fetch_lora(body: FetchBody) -> dict:
    """A LoRA from a link: a Hugging Face file link (https://huggingface.co/<repo>/resolve/<revision>/<file>.safetensors,
    the model chosen by the person) or a Civitai link (model, version or download; the model read from Civitai)."""
    link = body.url.strip()
    hf = _HF.match(link)
    if hf is None and _CIVITAI.match(link) is None:
        raise HTTPException(
            400, "Give a Hugging Face file link (…/resolve/<revision>/<file>.safetensors) or a Civitai model or download link"
        )
    if hf is not None and body.base not in BASES:
        raise HTTPException(400, "Choose the model the LoRA was made for")
    if hf is None:
        try:
            found = civitai_version(link)
        except (ValueError, httpx.HTTPError) as exc:
            raise HTTPException(400, f"Not added: {exc}") from exc
        if found["base"] is None:
            raise HTTPException(
                400,
                f"Not added: Civitai lists this LoRA for {found['civitaiBase'] or 'another model'}; formcut runs Krea 2 and FLUX.2 [klein] 4B",
            )
        if body.base and body.base != found["base"]:
            raise HTTPException(400, f"Not added: Civitai lists this LoRA for {found['civitaiBase']}, not {BASES[body.base]}")
        if found["bytes"] > MAX_BYTES:
            raise HTTPException(400, "Not added: a LoRA over 3 GB is not taken")

    def work(_job, report, cancelled):
        LIBRARY.mkdir(parents=True, exist_ok=True)
        part = LIBRARY / f".fetch-{time.time_ns()}.part"
        try:
            if hf is not None:
                repo, revision, name = hf.group(1), hf.group(2), hf.group(3)
                _download(f"https://huggingface.co/{repo}/resolve/{revision}/{name}", part, {}, report, cancelled)
                entry = add(
                    part,
                    body.name or Path(name).stem,
                    str(body.base),
                    f"https://huggingface.co/{repo} ({revision}) {name}",
                    {"originalFile": Path(name).name},
                )
            else:
                _download(found["download"], part, found["headers"], report, cancelled)
                entry = add(
                    part,
                    body.name or found["name"],
                    found["base"],
                    f"https://civitai.com/models (version {found['versionId']}) {found['file']}",
                    {"expectSha256": found["sha256"], "triggers": found["triggers"], "originalFile": found["file"]},
                )
            return {"lora": entry}
        finally:
            part.unlink(missing_ok=True)

    return jobs.submit("lora-fetch", work)


class EditBody(BaseModel):
    name: str | None = None
    scale: float | None = None
    triggers: str | None = None


def _file(base: str, stem: str) -> Path:
    path = LIBRARY / base / f"{stem}.safetensors"
    if base not in BASES or not re.fullmatch(r"[\w .()-]+", stem) or not path.is_file():
        raise HTTPException(404, "No such LoRA")
    return path


@router.patch("/{base}/{stem}")
def edit_lora(base: str, stem: str, body: EditBody) -> dict:
    path = _file(base, stem)
    record = _record(path)
    for key in ("name", "triggers"):
        if getattr(body, key) is not None:
            record[key] = str(getattr(body, key))[:200]
    if body.scale is not None:
        record["scale"] = max(SCALES[0], min(SCALES[1], float(body.scale)))
    path.with_suffix(".json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return next(e for e in entries(base) if e["file"] == path.name)


@router.delete("/{base}/{stem}")
def remove_lora(base: str, stem: str) -> dict:
    path = _file(base, stem)
    path.unlink()
    path.with_suffix(".json").unlink(missing_ok=True)
    return {"removed": f"{base}/{stem}"}
