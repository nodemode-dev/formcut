"""Krea 2 Turbo, an optional local image model.

Nothing of it is installed until a person asks. Installing it takes three decisions, recorded here in
models/krea-2-consent.json before a byte is downloaded:

1. The Krea 2 Community License Agreement is accepted (its terms are shown, with the link to them).
2. The content filter the licence requires (section 4.2) is installed and enabled, which formcut recommends:
   Falconsai/nsfw_image_detection, run on every picture (content_filter.py).
3. Or the filter is declined, and then only with the waiver below accepted: the person states that by their own
   choice they do not meet the licence's filtering requirement and that they, not formcut, its developers or
   NodeMode, are responsible for any violation and any misuse.

Whatever is chosen, a prompt that sexualises minors is refused before the model runs (prompt_refusal). That is
not a setting: no licence choice or waiver covers it.

The builds: on a Mac with Apple silicon, mflux-community's MLX quantisations run through mflux (8-bit, the higher
fidelity, or 4-bit for a Mac with less memory); on Windows and Linux, the 8-bit SDNQ quantisation of a
diffusers maintainer runs through diffusers' Krea2Pipeline. Each runs in its own Python environment under the
model's folder, so its packages (MLX, or PyTorch) never enter the engine's.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import jobs
from .paths import MODELS_DIR

router = APIRouter(prefix="/api/models/krea-2", tags=["models"])

FOLDER = MODELS_DIR / "krea-2"
CONSENT_FILE = MODELS_DIR / "krea-2-consent.json"
RUNTIME = FOLDER / "runtime"

LICENCE_NAME = "Krea 2 Community License Agreement"
LICENCE_VERSION = "v.1, June 22, 2026"
LICENCE_URL = "https://www.krea.ai/krea-2-licensing"
USE_POLICY_URL = "https://www.krea.ai/krea-2-use-policy"
# the attribution section 3.1(c) asks to be kept in a Notice file with the model
NOTICE = "Krea 2 is licensed under the Krea 2 Community License Agreement. For more information, visit https://krea.ai/krea-2-licensing."
LICENCE_SUMMARY = [
    (
        "Commercial use (of the model, anything derived from it, or its pictures) is permitted only while you, with any affiliated entities, have less than $1,000,000 USD of total annual revenue over the trailing twelve months; otherwise an enterprise licence from Krea is required first (section 2.3)."
    ),
    (
        "Whoever deploys the model must implement reasonable and appropriate content filter measures to detect, prevent and mitigate prohibited, harmful or unlawful content (section 4.2)."
    ),
    ("Use must follow Krea's Acceptable Use Policy and the law (sections 4.1 and 4.4)."),
    (
        'Distributing the model, or a product containing it, requires a copy of the agreement, the attribution notice, and a model name beginning with "Krea" (section 3.1).'
    ),
    ("The licence ends automatically on any breach, and Krea may end it on thirty days' notice (section 9)."),
    ("You own the pictures you make and are solely responsible for them; the model comes without warranty (sections 5.3 and 6)."),
]
FILTER = {
    "id": "nsfw-filter",
    "name": "Falconsai/nsfw_image_detection",
    "source": "onnx-community/nsfw_image_detection-ONNX",
    "licence": "Apache-2.0",
    "size": 343_401_688,
    "what": "An open-source classifier, named in section 4.2 of the licence, run on every picture Krea 2 makes; a picture "
    "it scores as NSFW is withheld and never reaches the library.",
}
WAIVER = (
    "I have chosen not to install and enable a content filter for Krea 2. I understand that section 4.2 of the Krea 2 "
    "Community License Agreement requires anyone who uses the model to implement reasonable and appropriate content "
    "filter measures, and that by my own choice I am not meeting that requirement, which is a breach of the licence "
    "and may end my rights under it (section 9.1). I accept sole responsibility for that choice, for every use I make "
    "of Krea 2 and of the pictures it makes, and for any violation of the Krea 2 Community License Agreement, of "
    "Krea's Acceptable Use Policy or of the law that results. formcut, its developers and NodeMode are not "
    "responsible for any misuse of the model or of formcut, and I will not hold them responsible for it."
)

# model: the model manager's entry; size in bytes; memory: the unified or system memory it wants, in GB
BUILDS = {
    "mlx-q8": {
        "model": "krea-2-mlx-q8",
        "label": "Krea 2 Turbo, 8-bit MLX",
        "platform": "macos-arm64",
        "size": 22_190_000_000,
        "memory": 32,
        "packages": ["mflux==0.20.0"],
        "note": "The higher-fidelity build for Apple silicon, run by mflux.",
    },
    "mlx-q4": {
        "model": "krea-2-mlx-q4",
        "label": "Krea 2 Turbo, 4-bit MLX",
        "platform": "macos-arm64",
        "size": 15_780_000_000,
        "memory": 16,
        "packages": ["mflux==0.20.0"],
        "note": "For a Mac with less than 32 GB of memory; 16 GB is tight.",
    },
    "sdnq-int8": {
        "model": "krea-2-sdnq-int8",
        "label": "Krea 2 Turbo, 8-bit SDNQ",
        "platform": "windows-linux",
        "size": 18_300_000_000,
        "memory": 32,
        "packages": ["diffusers>=0.40.0", "sdnq>=0.2.0", "transformers>=4.57.0", "accelerate>=1.10.0", "safetensors"],
        "note": "For Windows and Linux, run by diffusers; fastest on an NVIDIA GPU with 16 GB or more.",
    },
}
STEPS = 8  # Turbo is distilled to eight steps, guidance off


def machine() -> str:
    system = platform.system()
    if system == "Darwin":
        return "macos-arm64" if platform.machine() == "arm64" else "macos-intel"
    return "windows-linux" if system in ("Windows", "Linux") else system.lower()


def memory_gb() -> float:
    """The machine's memory, in GB (unified memory on Apple silicon)."""
    try:
        if platform.system() == "Windows":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                    (name, ctypes.c_ulonglong) for name in ("total", "free", "pagefile", "freepage", "virtual", "freevirtual", "extended")
                ]

            status = Status()
            status.length = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
            return status.total / 1e9
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1e9
    except (AttributeError, OSError, ValueError):
        return 0.0


def builds_here() -> list[str]:
    return [key for key, build in BUILDS.items() if build["platform"] == machine()]


def recommended() -> str | None:
    here = builds_here()
    if not here:
        return None
    if machine() == "macos-arm64":
        return "mlx-q8" if memory_gb() >= BUILDS["mlx-q8"]["memory"] else "mlx-q4"
    return here[0]


def consent() -> dict:
    try:
        return json.loads(CONSENT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def record_consent(accept_licence: bool, filter_choice: str, accept_waiver: bool) -> dict:
    """The three decisions, written before anything is downloaded; declining the filter needs the waiver."""
    if not accept_licence:
        raise ValueError(f"Krea 2 is installed only once the {LICENCE_NAME} is accepted")
    if filter_choice not in ("enable", "decline"):
        raise ValueError("choose whether to install and enable the content filter")
    if filter_choice == "decline" and not accept_waiver:
        raise ValueError("declining the content filter requires accepting the statement of responsibility")
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    record = {
        **consent(),
        "licence": {"name": LICENCE_NAME, "version": LICENCE_VERSION, "url": LICENCE_URL, "acceptedAt": now},
        "filter": "enabled" if filter_choice == "enable" else "declined",
        "waiver": None
        if filter_choice == "enable"
        else {"text": WAIVER, "sha256": hashlib.sha256(WAIVER.encode()).hexdigest(), "acceptedAt": now},
    }
    CONSENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONSENT_FILE.write_text(json.dumps(record, indent=1), encoding="utf-8")
    FOLDER.mkdir(parents=True, exist_ok=True)
    (FOLDER / "NOTICE.txt").write_text(NOTICE + "\n", encoding="utf-8")
    return record


def installed_build() -> str | None:
    from .model_manager import ready

    chosen = consent().get("build")
    if chosen in BUILDS and ready(BUILDS[chosen]["model"]) and _runtime_ready(chosen):
        return chosen
    return None


def policy() -> dict:
    """Whether Krea 2 may run now, and if not, why."""
    from . import content_filter

    record = consent()
    licence = bool(record.get("licence"))
    choice = record.get("filter")
    waiver = bool(record.get("waiver")) and (record["waiver"].get("sha256") == hashlib.sha256(WAIVER.encode()).hexdigest())
    build = installed_build()
    filter_ready = content_filter.installed()
    reason = None
    if not licence:
        reason = f"the {LICENCE_NAME} has not been accepted"
    elif choice not in ("enabled", "declined"):
        reason = "the content filter has not been chosen"
    elif choice == "enabled" and not filter_ready:
        reason = "the content filter is enabled but not installed"
    elif choice == "declined" and not waiver:
        reason = "the content filter was declined without the statement of responsibility"
    elif build is None:
        reason = "no Krea 2 build is installed"
    return {
        "licenceAccepted": licence,
        "filter": choice,
        "filterInstalled": filter_ready,
        "waiverOnRecord": waiver,
        "build": build,
        "ready": reason is None,
        "reason": reason,
    }


# Refused whatever the settings: sexual content involving minors. The two lists are ordinary words, deliberately
# plain; the model's own acceptable use policy and the law forbid far more, which the filter and the person's own
# responsibility cover.
_MINOR = re.compile(
    r"\b(child|children|kid|kids|minor|minors|underage|under-age|preteen|pre-teen|toddler|infant|baby|schoolgirl|schoolboy|"
    r"(?:[1-9]|1[0-7])[- ]?(?:year|yr)s?[- ]?old)\b",
    re.IGNORECASE,
)
_SEXUAL = re.compile(
    r"\b(nude|nudity|naked|sex|sexual|sexy|nsfw|porn|pornographic|explicit|erotic|lingerie|topless|undressed)\b", re.IGNORECASE
)


def prompt_refusal(prompt: str) -> str | None:
    if _MINOR.search(prompt or "") and _SEXUAL.search(prompt or ""):
        return "This prompt is refused: formcut will not generate sexual content involving minors, whatever the content filter setting."
    return None


def _runtime_python() -> Path:
    return RUNTIME / ("Scripts/python.exe" if platform.system() == "Windows" else "bin/python")


def _runtime_ready(build: str) -> bool:
    marker = RUNTIME / "installed.json"
    try:
        return _runtime_python().is_file() and build in json.loads(marker.read_text(encoding="utf-8")).get("builds", [])
    except (OSError, ValueError):
        return False


def _base_python() -> str:
    """A Python to make the model's own environment with: this one, unless the engine is a frozen app."""
    if not getattr(sys, "frozen", False):
        return sys.executable
    found = shutil.which("python3") or shutil.which("python")
    if not found:
        raise RuntimeError("Krea 2 runs in its own Python environment; install Python 3.10 or later and try again")
    return found


def install_runtime(build: str, report) -> None:
    """The build's packages, in an environment of the model's own under models/krea-2/runtime."""
    python = _runtime_python()
    if not python.is_file():
        subprocess.run([_base_python(), "-m", "venv", str(RUNTIME)], check=True, capture_output=True)
    report(0.2)
    pip = [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--upgrade"]
    if BUILDS[build]["platform"] == "windows-linux":
        # PyTorch first: on Windows the default index carries the CPU build, so an NVIDIA machine takes CUDA's
        index = (
            ["--index-url", "https://download.pytorch.org/whl/cu128"]
            if platform.system() == "Windows" and shutil.which("nvidia-smi")
            else []
        )
        subprocess.run([*pip, "torch", *index], check=True, capture_output=True)
        report(0.6)
    subprocess.run([*pip, *BUILDS[build]["packages"]], check=True, capture_output=True)
    marker = RUNTIME / "installed.json"
    try:
        done = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        done = {}
    done["builds"] = sorted({*done.get("builds", []), build})
    marker.write_text(json.dumps(done), encoding="utf-8")
    report(1.0)


def install(build: str, report, cancelled) -> dict:
    """The job: the build's files (pinned), its environment, and the content filter when it was chosen."""
    from .model_manager import download

    state = consent()
    if not state.get("licence") or state.get("filter") not in ("enabled", "declined"):
        raise ValueError("record the licence and the content filter choice before installing Krea 2")
    with_filter = state.get("filter") == "enabled"
    share = (0.8, 0.95) if with_filter else (0.9, 1.0)
    download(BUILDS[build]["model"], lambda f: report(f * share[0]), cancelled)
    if with_filter:
        download(FILTER["id"], lambda f: report(share[0] + f * (share[1] - share[0])), cancelled)
    install_runtime(build, lambda f: report(share[1] + f * (1 - share[1])))
    CONSENT_FILE.write_text(json.dumps({**consent(), "build": build}, indent=1), encoding="utf-8")
    return policy()


_DIFFUSERS_RUNNER = """
import sys, torch
from diffusers import Krea2Pipeline
from sdnq import SDNQConfig  # noqa: F401  (registers SDNQ's quantisation with diffusers and transformers)
folder, prompt, width, height, seed, steps, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7]
pipe = Krea2Pipeline.from_pretrained(folder, torch_dtype=torch.bfloat16)
if torch.cuda.is_available():
    free = torch.cuda.get_device_properties(0).total_memory / 1e9
    pipe.to("cuda") if free >= 20 else pipe.enable_model_cpu_offload()
elif hasattr(torch, "xpu") and torch.xpu.is_available():
    pipe.to("xpu")
generator = torch.Generator(device="cpu").manual_seed(seed)
image = pipe(prompt=prompt, width=width, height=height, num_inference_steps=steps, guidance_scale=1.0, generator=generator).images[0]
image.save(out)
"""


def _command(build: str, prompt: str, out: Path, width: int, height: int, seed: int, steps: int) -> list[str]:
    from .model_manager import ROOT

    folder = ROOT / BUILDS[build]["model"]
    if BUILDS[build]["platform"] == "macos-arm64":
        cli = RUNTIME / "bin" / "mflux-generate-krea2"
        return [
            str(cli),
            "--model",
            str(folder),
            "--base-model",
            "krea-2",
            "--prompt",
            prompt,
            "--width",
            str(width),
            "--height",
            str(height),
            "--seed",
            str(seed),
            "--steps",
            str(steps),
            "--output",
            str(out),
        ]
    return [str(_runtime_python()), "-c", _DIFFUSERS_RUNNER, str(folder), prompt, str(width), str(height), str(seed), str(steps), str(out)]


def generate_to_file(
    prompt: str, path: Path, width: int = 1024, height: int = 1024, seed: int | None = None, steps: int | None = None, **_options
) -> dict:
    """One picture, under the recorded choices: refused prompts never run, and with the filter enabled a picture it
    scores as NSFW is deleted and reported instead of returned."""
    from PIL import Image

    from . import content_filter

    state = policy()
    if not state["ready"]:
        raise RuntimeError(f"Krea 2 cannot run: {state['reason']}")
    refusal = prompt_refusal(prompt)
    if refusal:
        raise ValueError(refusal)
    started = time.time()
    seed = int(seed) if seed is not None else int.from_bytes(os.urandom(4), "little")
    # Krea 2 works in multiples of 16; the panel's sizes are
    width, height = max(256, int(width) // 16 * 16), max(256, int(height) // 16 * 16)
    done = subprocess.run(
        _command(state["build"], prompt, path, width, height, seed, int(steps or STEPS)), capture_output=True, text=True, check=False
    )
    if done.returncode or not path.is_file():
        raise RuntimeError("Krea 2 did not make a picture: " + (done.stderr or done.stdout)[-600:])
    verdict = None
    if state["filter"] == "enabled":
        import numpy as np

        verdict = content_filter.check(np.asarray(Image.open(path).convert("RGB")))
        if verdict["withheld"]:
            path.unlink(missing_ok=True)
            raise ValueError(f"The content filter withheld this picture (NSFW score {verdict['nsfw']:.2f}).")
    with Image.open(path) as picture:
        size = picture.size
    return {
        "path": str(path),
        "model": "krea-2",
        "provider": BUILDS[state["build"]]["label"],
        "seconds": round(time.time() - started, 1),
        "width": size[0],
        "height": size[1],
        "seed": seed,
        "contentFilter": verdict or "declined by the user, with the statement of responsibility on record",
        "notice": NOTICE,
    }


class ConsentBody(BaseModel):
    acceptLicence: bool = False
    filter: str = ""
    acceptWaiver: bool = False


class InstallBody(BaseModel):
    build: str | None = None


@router.get("/terms")
def terms() -> dict:
    """What a person reads before installing: the licence's terms, the filter, the waiver, the builds for this machine."""
    return {
        "licence": {
            "name": LICENCE_NAME,
            "version": LICENCE_VERSION,
            "url": LICENCE_URL,
            "usePolicy": USE_POLICY_URL,
            "summary": LICENCE_SUMMARY,
        },
        "notice": NOTICE,
        "filter": FILTER,
        "waiver": WAIVER,
        "builds": {key: {k: v for k, v in BUILDS[key].items() if k != "packages"} for key in builds_here()},
        "recommended": recommended(),
        "memoryGB": round(memory_gb(), 1),
        "policy": policy(),
    }


@router.get("/status")
def status() -> dict:
    return policy()


@router.post("/consent")
def give_consent(body: ConsentBody) -> dict:
    try:
        record_consent(body.acceptLicence, body.filter, body.acceptWaiver)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return policy()


@router.post("/install", status_code=202)
def start_install(body: InstallBody) -> dict:
    build = body.build or recommended()
    if build not in builds_here():
        raise HTTPException(400, f"no Krea 2 build for this machine ({machine()})")
    state = consent()
    if not state.get("licence") or state.get("filter") not in ("enabled", "declined"):
        raise HTTPException(409, "accept the licence and choose the content filter first")
    return jobs.submit("krea-2-install", lambda _id, report, cancelled: install(build, report, cancelled))


@router.post("/filter", status_code=202)
def enable_filter() -> dict:
    """Turn the content filter on after declining it: the waiver is withdrawn and the classifier fetched."""
    from .model_manager import download

    record = consent()
    if not record.get("licence"):
        raise HTTPException(409, "accept the licence first")
    CONSENT_FILE.write_text(json.dumps({**record, "filter": "enabled", "waiver": None}, indent=1), encoding="utf-8")
    return jobs.submit("model-download", lambda _id, report, cancelled: download(FILTER["id"], report, cancelled))
