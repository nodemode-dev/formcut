"""FLUX.2 [klein] 4B and 9B, local, on Apple silicon through mflux, with LoRA stacks.

Two optional models from Black Forest Labs, neither shipped nor distributed with formcut: their MLX builds are fetched
from mflux-community on Hugging Face (the publisher of formcut's Krea 2 builds), pinned file by file to a revision,
when a person installs them from their card in Studio > Local models, and run by the same mflux environment as Krea 2
(models/krea-2/runtime, installed here if Krea 2 has not installed it), through mflux-generate-flux2.

- 4B: Apache License 2.0, commercial use allowed. Black Forest Labs encourages a content filter; the filter formcut
  installs with Krea 2 runs on 4B's pictures too whenever it is installed.
- 9B: the FLUX Non-Commercial License v2.1: the model may be used for non-commercial purposes only (its outputs may be
  used for any purpose the licence does not prohibit), and filters or manual review must be used with it. As with
  Krea 2: the licence is accepted before anything downloads, the content filter installs with it, and a filter the
  person removes afterwards leaves the model running with a warning that the removal and the responsibility are
  theirs. A prompt sexualising minors is refused before either model runs, whatever else is set.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import jobs, krea2, local_runner, loras
from .model_manager import ROOT as MODELS_DIR

router = APIRouter(prefix="/api/models/klein", tags=["models"])
CONSENT_FILE = MODELS_DIR / "klein-consent.json"
STEPS = 4  # both are distilled to four steps, guidance 1.0
SIZES = ["1024x1024", "1344x768", "768x1344", "1536x1024", "1024x1536", "512x512"]

NC = "FLUX Non-Commercial License v2.1"
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
    "flux2-klein-9b": {
        "label": "FLUX.2 [klein] 9B",
        "licence": {
            "name": NC,
            "url": "https://huggingface.co/black-forest-labs/FLUX.2-klein-9B",
            "commercial": False,
            "summary": [
                "The FLUX Non-Commercial License v2.1: the model may be used only for non-commercial purposes; a commercial licence is at https://bfl.ai/licensing.",
                "The pictures it makes may be used for any purpose, commercial ones included, except as the licence prohibits.",
                "Filters or manual review must be used with the 9B models: formcut installs its content filter with it.",
                "Black Forest Labs claims no ownership of the pictures; you are responsible for them and their use.",
            ],
        },
        "filterRequired": True,
        "builds": {
            "mlx-q8": {
                "model": "flux2-klein-9b-mlx-q8",
                "label": "8-bit MLX",
                "bytes": 17_865_574_635,
                "note": "best quality, 32 GB of memory or more",
            },
            "mlx-q4": {"model": "flux2-klein-9b-mlx-q4", "label": "4-bit MLX", "bytes": 9_541_191_417, "note": "for 16 to 24 GB of memory"},
        },
    },
}

REMOVED_WARNING_9B = (
    "The content filter has been removed. The FLUX Non-Commercial License requires filters or manual review to be used "
    "with FLUX.2 [klein] 9B, and formcut installs Falconsai/nsfw_image_detection with it to run on every picture. It is no "
    "longer present on this computer or in this build of formcut, which means it was knowingly removed, by you or on "
    "your behalf. The model will keep running without it. Without the filter, reviewing every picture yourself is the "
    "way left to meet that requirement; you alone are responsible for that, for every use you make of the model and "
    "its pictures, and for any violation of the licence or of any law, in any jurisdiction. formcut is open-source "
    'software provided under the Apache License, Version 2.0, "as is" and without warranty; formcut, its developers '
    "and NodeMode do not ship or distribute FLUX.2 [klein] and, to the fullest extent permitted by law, are not "
    "responsible for, and cannot be held liable for, how you use or modify formcut or the models you install with it. "
    "To put the filter back, choose Reinstall the content filter."
)


def _is_apple_silicon() -> bool:
    return os.uname().sysname == "Darwin" and os.uname().machine == "arm64" if hasattr(os, "uname") else False


def consent() -> dict:
    try:
        return json.loads(CONSENT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(record: dict) -> None:
    CONSENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONSENT_FILE.write_text(json.dumps(record, indent=1), encoding="utf-8")


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


def _warning_hash() -> str:
    return hashlib.sha256(REMOVED_WARNING_9B.encode()).hexdigest()


def policy(variant: str) -> dict:
    from . import content_filter

    spec = VARIANTS[variant]
    record = consent().get(variant, {})
    licence = bool(record.get("licence"))
    build = installed_build(variant)
    filter_ready = content_filter.installed()
    removed = spec["filterRequired"] and build is not None and not filter_ready
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
        "removalAcknowledged": (record.get("removalAcknowledged") or {}).get("sha256") == _warning_hash(),
        "warning": REMOVED_WARNING_9B if removed else None,
        "ready": reason is None,
        "reason": reason,
    }


def install(variant: str, build: str, report, cancelled) -> dict:
    """The build's files (pinned), the content filter for 9B (always), and the mflux environment if not there yet."""
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
) -> dict:
    from PIL import Image

    from . import content_filter

    spec = VARIANTS[variant]
    state = policy(variant)
    if not state["ready"]:
        raise RuntimeError(f"{spec['label']} cannot run: {state['reason']}")
    refusal = krea2.prompt_refusal(prompt)
    if refusal:
        raise ValueError(refusal)
    started = time.time()
    seed = int(seed) if seed is not None else int.from_bytes(os.urandom(4), "little")
    width, height = max(256, int(width) // 16 * 16), max(256, int(height) // 16 * 16)
    build = spec["builds"][state["build"]]
    settings = local_runner.plan(build["bytes"], memory)
    steps = max(1, min(50, int(steps or STEPS)))
    command = [
        str(_cli()),
        "--model", str(MODELS_DIR / build["model"]),
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
    local_runner.run(command, steps, report, cancelled, spec["label"])
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
        "notice": None
        if spec["licence"]["commercial"]
        else f"{spec['label']} is licensed under the {NC}; the model is for non-commercial use.",
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
            "removedWarning": REMOVED_WARNING_9B if spec["filterRequired"] else None,
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


class VariantBody(BaseModel):
    variant: str


@router.post("/acknowledge-removal")
def acknowledge(body: VariantBody) -> dict:
    if body.variant not in VARIANTS:
        raise HTTPException(400, "Unknown model")
    record = consent()
    record.setdefault(body.variant, {})["removalAcknowledged"] = {
        "sha256": _warning_hash(),
        "acknowledgedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    }
    _save(record)
    return policy(body.variant)
