"""FLUX.2 [klein] 4B, local, on Apple silicon through mflux, with LoRA stacks.

An optional model from Black Forest Labs, neither shipped nor distributed with formcut: its MLX builds are fetched
from mflux-community on Hugging Face (the publisher of formcut's Krea 2 builds), pinned file by file to a revision,
when a person installs it from its card in Studio > Local models, and run by the same mflux environment as Krea 2
(models/krea-2/runtime, installed here if Krea 2 has not installed it), through mflux-generate-flux2.

Only the 4B, by the owner's choice: it is under the Apache License 2.0, commercial use allowed. The 9B models are
under the FLUX Non-Commercial License, which does not fit a tool people use for paid work, so formcut does not offer
them. Black Forest Labs encourages a content filter with 4B; the filter formcut installs with Krea 2 runs on 4B's
pictures whenever it is installed. A prompt sexualising minors is refused before the model runs, whatever else is set.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import jobs, krea2, local_runner, loras
from .durable import read_json, write_json
from .model_manager import ROOT as MODELS_DIR

router = APIRouter(prefix="/api/models/klein", tags=["models"])
CONSENT_FILE = MODELS_DIR / "klein-consent.json"
STEPS = 4  # both are distilled to four steps, guidance 1.0
SIZES = ["1024x1024", "1344x768", "768x1344", "1536x1024", "1024x1536", "512x512"]

VARIANTS = {
    "flux2-klein-4b": {
        "label": "FLUX.2 [klein] 4B",
        "licence": {
            "name": "Apache License 2.0",
            "url": "https://huggingface.co/black-forest-labs/FLUX.2-klein-4B",
            "commercial": True,
            "summary": [
                "Apache License 2.0: use, change and share the model, including for commercial work.",
                "Black Forest Labs encourages a content filter; formcut runs its filter on 4B's pictures when it is installed.",
                "Pictures you make are yours to use; you are responsible for them and for how you use them.",
            ],
        },
        "filterRequired": False,
        "builds": {
            "mlx-q8": {
                "model": "flux2-klein-4b-mlx-q8",
                "label": "8-bit MLX",
                "bytes": 8_569_652_902,
                "note": "best quality, 16 GB of memory or more",
            },
            "mlx-q4": {"model": "flux2-klein-4b-mlx-q4", "label": "4-bit MLX", "bytes": 4_619_699_678, "note": "smallest and quickest"},
        },
    },
}


def _is_apple_silicon() -> bool:
    return os.uname().sysname == "Darwin" and os.uname().machine == "arm64" if hasattr(os, "uname") else False


def consent() -> dict:
    try:
        return read_json(CONSENT_FILE, {})  # durable.py: set aside when damaged, the backup read
    except (OSError, ValueError):
        return {}


def _save(record: dict) -> None:
    write_json(CONSENT_FILE, record, indent=1)


def record_consent(variant: str, accept_licence: bool) -> dict:
    if variant not in VARIANTS:
        raise ValueError("unknown model")
    if not accept_licence:
        raise ValueError(f"{VARIANTS[variant]['label']} is installed only once its licence is accepted")
    record = consent()
    record[variant] = {
        **record.get(variant, {}),
        "licence": {"name": VARIANTS[variant]["licence"]["name"], "acceptedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z")},
    }
    _save(record)
    return policy(variant)


def _cli() -> Path:
    return krea2.RUNTIME / "bin" / "mflux-generate-flux2"


def installed_build(variant: str) -> str | None:
    from .model_manager import ready

    if not _cli().is_file():
        return None
    for build, spec in VARIANTS[variant]["builds"].items():
        if ready(spec["model"]):
            return build
    return None


def policy(variant: str) -> dict:
    from . import content_filter

    spec = VARIANTS[variant]
    record = consent().get(variant, {})
    licence = bool(record.get("licence"))
    build = installed_build(variant)
    filter_ready = content_filter.installed()
    removed = False  # no filter is required of 4B; it runs whenever installed
    reason = None
    if not _is_apple_silicon():
        reason = "FLUX.2 [klein] runs here on Apple silicon (mflux); on Windows and Linux it is not offered yet"
    elif not licence:
        reason = f"the {spec['licence']['name']} has not been accepted"
    elif build is None:
        reason = f"no {spec['label']} build is installed"
    return {
        "variant": variant,
        "licenceAccepted": licence,
        "build": build,
        "filterInstalled": filter_ready,
        "filterRemoved": removed,
        "warning": None,
        "ready": reason is None,
        "reason": reason,
    }


def install(variant: str, build: str, report, cancelled) -> dict:
    """The build's files (pinned) and the mflux environment if not there yet."""
    from .model_manager import download

    spec = VARIANTS[variant]
    if not consent().get(variant, {}).get("licence"):
        raise ValueError("accept the licence first")
    if spec["filterRequired"]:
        download(krea2.FILTER["id"], lambda f: report(f * 0.02), cancelled)
    download(spec["builds"][build]["model"], lambda f: report(0.02 + f * 0.9), cancelled)
    if not _cli().is_file():
        krea2.install_runtime("mlx-q8", lambda f: report(0.92 + f * 0.08))
    return policy(variant)


def generate_to_file(
    variant: str,
    prompt: str,
    path: Path,
    width: int = 1024,
    height: int = 1024,
    seed: int | None = None,
    steps: int | None = None,
    stack: list | None = None,
    memory: str = "auto",
    report=lambda *_: None,
    cancelled=lambda: False,
    folder: Path | None = None,
) -> dict:
    from PIL import Image

    from . import content_filter

    spec = VARIANTS[variant]
    state = policy(variant)
    if folder is not None:
        # a checkpoint of the person's own (checkpoints.py): mflux, not a pinned build
        if not _is_apple_silicon():
            raise RuntimeError("Klein checkpoints run on Apple silicon (mflux)")
        if not _cli().is_file():
            raise RuntimeError("Install FLUX.2 [klein] 4B or Krea 2 once from its card: that sets up mflux, which runs checkpoints")
    elif not state["ready"]:
        raise RuntimeError(f"{spec['label']} cannot run: {state['reason']}")
    refusal = krea2.prompt_refusal(prompt)
    if refusal:
        raise ValueError(refusal)
    started = time.time()
    seed = int(seed) if seed is not None else int.from_bytes(os.urandom(4), "little")
    width, height = max(256, int(width) // 16 * 16), max(256, int(height) // 16 * 16)
    build = spec["builds"].get(state["build"] or "") or {"label": f"checkpoint {folder.name}" if folder else "", "bytes": 0, "model": ""}
    size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder else build["bytes"]
    settings = local_runner.plan(int(size), memory)
    steps = max(1, min(50, int(steps or STEPS)))
    command = [
        str(_cli()),
        "--model", str(folder or MODELS_DIR / build["model"]),
        "--base-model", variant,
        "--prompt", prompt,
        "--width", str(width),
        "--height", str(height),
        "--seed", str(seed),
        "--steps", str(steps),
        "--guidance", "1.0",
        "--output", str(path),
        *loras.mflux_flags(loras.resolve(stack, variant)),
        *local_runner.mflux_memory_flags(settings),
    ]  # fmt: skip
    local_runner.run(command, steps, report, cancelled, f"{spec['label']} checkpoint {folder.name}" if folder else spec["label"])
    if not path.is_file():
        raise RuntimeError(f"{spec['label']} finished without a picture")
    verdict = None
    if state["filterInstalled"]:
        import numpy as np

        verdict = content_filter.check(np.asarray(Image.open(path).convert("RGB")))
        if verdict["withheld"]:
            path.unlink(missing_ok=True)
            raise ValueError(f"The content filter withheld this picture (NSFW score {verdict['nsfw']:.2f}).")
    with Image.open(path) as picture:
        size = picture.size
    return {
        "path": str(path),
        "model": variant,
        "provider": f"{spec['label']}, {build['label']}",
        "seconds": round(time.time() - started, 1),
        "width": size[0],
        "height": size[1],
        "seed": seed,
        "memory": settings,
        "contentFilter": verdict or ("removed" if spec["filterRequired"] else "not installed"),
        "warning": state["warning"],
        "notice": None,
    }


@router.get("/terms")
def terms() -> dict:
    from .model_manager import MODELS

    out = {}
    for variant, spec in VARIANTS.items():
        out[variant] = {
            "label": spec["label"],
            "licence": spec["licence"],
            "filterRequired": spec["filterRequired"],
            "builds": {key: {**build, "available": build["model"] in MODELS} for key, build in spec["builds"].items()},
            "status": policy(variant),
        }
    return {"variants": out, "memory": local_runner.plan(0)}


class ConsentBody(BaseModel):
    variant: str
    acceptLicence: bool = False


@router.post("/consent")
def accept(body: ConsentBody) -> dict:
    try:
        return record_consent(body.variant, body.acceptLicence)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


class InstallBody(BaseModel):
    variant: str
    build: str = "mlx-q8"


@router.post("/install", status_code=202)
def start_install(body: InstallBody) -> dict:
    spec = VARIANTS.get(body.variant)
    if spec is None or body.build not in spec["builds"]:
        raise HTTPException(400, "Unknown model or build")
    if not consent().get(body.variant, {}).get("licence"):
        raise HTTPException(409, "accept the licence first")
    return jobs.submit("klein-install", lambda _id, report, cancelled: install(body.variant, body.build, report, cancelled))
