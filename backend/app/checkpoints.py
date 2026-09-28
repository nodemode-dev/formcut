"""Checkpoints of a person's own: fine-tunes of Krea 2 or FLUX.2 [klein] 4B, converted to mflux's MLX format.

Dropped into the folder of the model they were made from, one folder each:

    models/checkpoints/krea-2/<name>/            (a Krea 2 fine-tune, e.g. silly_krea2)
    models/checkpoints/flux2-klein-4b/<name>/    (a Klein 4B fine-tune)

"The correct MLX format" is the folder mflux itself writes (mflux-save, or any mflux-community build): text_encoder/,
tokenizer/ and vae/, each with its files, and the transformer's weights either in transformer/ (Klein's layout) or at
the folder's top (Krea 2's), as *.safetensors. check() says what is missing; a single .safetensors file (a ComfyUI or
Automatic1111 checkpoint as Civitai serves it) is named for what it is: it has to be converted first, which the models
page describes. Each checkpoint appears in the image generator as a model of its own, runs through the same mflux as
its base model (installed with Krea 2 or Klein 4B), and takes that model's LoRAs.

A Krea 2 fine-tune is a derivative of Krea 2, so its licence applies: a Krea 2 checkpoint runs once the Krea 2
Community License Agreement has been accepted on the Krea 2 card, and the content filter runs on its pictures as on
Krea 2's (or its warning, if the filter was removed). A Klein 4B fine-tune carries its own licence, which is its
author's and the person's to honour.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter

from .model_manager import ROOT

router = APIRouter(prefix="/api/checkpoints", tags=["models"])

FOLDER = ROOT / "checkpoints"
BASES = {"krea-2": "Krea 2", "flux2-klein-4b": "FLUX.2 [klein] 4B"}


def _weights(folder: Path) -> list[Path]:
    return sorted(folder.glob("*.safetensors")) if folder.is_dir() else []


def check(folder: Path) -> str | None:
    """What keeps a folder from being an mflux checkpoint, or None when it is one."""
    missing = [part for part in ("text_encoder", "vae") if not _weights(folder / part)]
    if not (folder / "tokenizer").is_dir() or not any((folder / "tokenizer").iterdir()):
        missing.append("tokenizer")
    if not (_weights(folder / "transformer") or _weights(folder)):
        missing.append("the transformer's weights (transformer/*.safetensors, or *.safetensors at the top)")
    if missing:
        return "not in mflux's MLX format: missing " + ", ".join(missing)
    return None


def entries(base: str | None = None) -> list[dict]:
    out = []
    for key in BASES if base is None else [base] if base in BASES else []:
        root = FOLDER / key
        root.mkdir(parents=True, exist_ok=True)  # there to drop into
        for item in sorted(root.iterdir()):
            if item.name.startswith("."):
                continue
            if item.is_file() and item.suffix == ".safetensors":
                problem = "a single .safetensors file: convert it to mflux's MLX format (a folder) first; see the Models page"
            elif item.is_dir():
                problem = check(item)
            else:
                continue
            size = sum(p.stat().st_size for p in item.rglob("*") if p.is_file()) if item.is_dir() else item.stat().st_size
            out.append(
                {
                    "id": f"ckpt:{key}:{item.name}",
                    "name": item.name,
                    "base": key,
                    "baseLabel": BASES[key],
                    "folder": str(item),
                    "bytes": size,
                    "usable": problem is None,
                    "problem": problem,
                }
            )
    return out


def find(base: str, name: str) -> dict | None:
    """A usable checkpoint of this base by name, the way a generation's "Model:" names it."""
    plain = re.sub(r"[\s_\-.]+", "", name).lower()
    for entry in entries(base):
        if entry["usable"] and (entry["name"] == name or re.sub(r"[\s_\-.]+", "", entry["name"]).lower() == plain):
            return entry
    return None


@router.get("")
def list_checkpoints() -> dict:
    return {"checkpoints": entries(), "folders": {key: str(FOLDER / key) for key in BASES}, "bases": BASES}
