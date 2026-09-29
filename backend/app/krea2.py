"""Krea 2 Turbo, an optional local image model.

formcut neither ships nor distributes Krea 2: its weights are fetched from their publishers on Hugging Face, onto
the person's own computer, when that person asks. Installing it takes one decision, recorded in
models/krea-2-consent.json before a byte is downloaded: the Krea 2 Community License Agreement accepted (its
terms shown, with the link to them). The content filter that licence requires (section 4.2),
Falconsai/nsfw_image_detection, is always installed with it and runs on every picture (content_filter.py); there
is no option to install Krea 2 without it.

A person may still remove the filter afterwards (delete its files, or change their own build of this open-source
program). Krea 2 then keeps running: the removal was theirs, knowingly made, and the Krea card and every picture
made without the filter carry REMOVED_WARNING, which the person may acknowledge (the acknowledgement is recorded
with a hash of its wording). "Reinstall the content filter" puts it back.

Whatever else happens, a prompt that sexualises minors is refused before the model runs (prompt_refusal). That is
not a setting and cannot be removed by removing the filter.

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
    "what": "An open-source classifier, named in section 4.2 of the licence, installed with Krea 2 and run on every picture "
    "it makes; a picture it scores as NSFW is withheld and never reaches the library.",
}
# Shown when Krea 2 runs and the filter formcut installed with it is no longer there.
REMOVED_WARNING = (
    "The content filter has been removed. formcut installs Falconsai/nsfw_image_detection with Krea 2 and runs it on "
    "every picture Krea 2 makes, as section 4.2 of the Krea 2 Community License Agreement requires of anyone who uses "
    "the model. It is no longer present on this computer or in this build of formcut, which means it was knowingly "
    "removed, by you or on your behalf. Krea 2 will keep running without it. By using Krea 2 without it you are not "
    "meeting the licence's filtering requirement, which is a breach of that licence and may end your rights under it "
    "(section 9.1). You alone are responsible for that decision, for every use you make of Krea 2 and of the pictures "
    "it makes, and for any violation of the Krea 2 Community License Agreement, of Krea's Acceptable Use Policy, or "
    "of any law, in any jurisdiction. formcut is open-source software provided under the Apache License, Version 2.0, "
    '"as is" and without warranty. formcut, its developers and NodeMode do not ship or distribute Krea 2, and, to '
    "the fullest extent permitted by law, are not responsible for, and cannot be held liable for, how you use or "
    "modify formcut or the models you install with it. To put the filter back, choose Reinstall the content filter."
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


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def record_consent(accept_licence: bool) -> dict:
    """The licence accepted, written before anything is downloaded; the content filter comes with the model."""
    if not accept_licence:
        raise ValueError(f"Krea 2 is installed only once the {LICENCE_NAME} is accepted")
    record = {
        **consent(),
        "licence": {"name": LICENCE_NAME, "version": LICENCE_VERSION, "url": LICENCE_URL, "acceptedAt": _now()},
        "filter": "installed with Krea 2",
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


def _warning_hash() -> str:
    return hashlib.sha256(REMOVED_WARNING.encode()).hexdigest()


def policy() -> dict:
    """Whether Krea 2 may run now, and if not, why; and whether its content filter is still there. A removed filter
    does not stop it: that removal was the person's own, and the warning says so."""
    from . import content_filter

    record = consent()
    licence = bool(record.get("licence"))
    build = installed_build()
    filter_ready = content_filter.installed()
    removed = build is not None and not filter_ready
    acknowledged = (record.get("removalAcknowledged") or {}).get("sha256") == _warning_hash()
    reason = None
    if not licence:
        reason = f"the {LICENCE_NAME} has not been accepted"
    elif build is None:
        reason = "no Krea 2 build is installed"
    return {
        "licenceAccepted": licence,
        "filterInstalled": filter_ready,
        "filterRemoved": removed,
        "removalAcknowledged": acknowledged,
        "warning": REMOVED_WARNING if removed else None,
        "build": build,
        "ready": reason is None,
        "reason": reason,
    }


def acknowledge_removal() -> dict:
    """The person's acknowledgement of the warning, with the time and a hash of the wording they saw."""
    record = consent()
    record["removalAcknowledged"] = {"sha256": _warning_hash(), "text": REMOVED_WARNING, "acknowledgedAt": _now()}
    CONSENT_FILE.write_text(json.dumps(record, indent=1), encoding="utf-8")
    return policy()


def _note_run_without_filter() -> None:
    """Every run without the filter is counted, first and last, beside the acknowledgement."""
    record = consent()
    runs = record.get("runsWithoutFilter") or {"first": _now(), "count": 0}
    runs["count"] = int(runs.get("count", 0)) + 1
    runs["last"] = _now()
    record["runsWithoutFilter"] = runs
    CONSENT_FILE.write_text(json.dumps(record, indent=1), encoding="utf-8")


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
    """The job: the build's files (pinned), the content filter (always), and the build's own environment."""
    from .model_manager import download

    if not consent().get("licence"):
        raise ValueError("accept the licence before installing Krea 2")
    download(FILTER["id"], lambda f: report(f * 0.02), cancelled)
    download(BUILDS[build]["model"], lambda f: report(0.02 + f * 0.93), cancelled)
    install_runtime(build, lambda f: report(0.95 + f * 0.05))
    CONSENT_FILE.write_text(json.dumps({**consent(), "build": build}, indent=1), encoding="utf-8")
    return policy()


_DIFFUSERS_RUNNER = """
import json, sys, torch
from diffusers import Krea2Pipeline
from sdnq import SDNQConfig  # noqa: F401  (registers SDNQ's quantisation with diffusers and transformers)
folder, prompt, width, height, seed, steps, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7]
pipe = Krea2Pipeline.from_pretrained(folder, torch_dtype=torch.bfloat16)
if torch.cuda.is_available():
    free = torch.cuda.get_device_properties(0).total_memory / 1e9
    pipe.to("cuda") if free >= 20 else pipe.enable_model_cpu_offload()
elif hasattr(torch, "xpu") and torch.xpu.is_available():
    pipe.to("xpu")
pairs = json.loads(sys.argv[8]) if len(sys.argv) > 8 else []
if pairs:
    names = [f"lora{i}" for i in range(len(pairs))]
    for name, (path, _scale) in zip(names, pairs):
        pipe.load_lora_weights(path, adapter_name=name)
    pipe.set_adapters(names, adapter_weights=[scale for _path, scale in pairs])
generator = torch.Generator(device="cpu").manual_seed(seed)
image = pipe(prompt=prompt, width=width, height=height, num_inference_steps=steps, guidance_scale=1.0, generator=generator).images[0]
image.save(out)
"""


def _command(
    build: str,
    prompt: str,
    out: Path,
    width: int,
    height: int,
    seed: int,
    steps: int,
    pairs: list | None = None,
    settings: dict | None = None,
    checkpoint: Path | None = None,
    seeds: list[int] | None = None,
    sampling: dict | None = None,
    prompt_file: Path | None = None,
) -> list[str]:
    from . import local_runner
    from .model_manager import ROOT

    folder = checkpoint or ROOT / BUILDS[build]["model"]
    pairs = pairs or []
    if BUILDS[build]["platform"] != "macos-arm64":
        # diffusers: the LoRAs as JSON after the usual arguments, loaded with their strengths
        return [
            str(_runtime_python()),
            "-c",
            _DIFFUSERS_RUNNER,
            str(folder),
            prompt,
            str(width),
            str(height),
            str(seed),
            str(steps),
            str(out),
            json.dumps(pairs),
        ]
    # mflux-generate-krea2 as mflux 0.20.0 parses it (the owner's list, from its argument parser): a local folder needs
    # no --base-model; several seeds render in one load; --lora PATH SCALE once per LoRA (negative for sliders);
    # --no-bake-lora keeps a 4-bit model 4-bit; --scheduler is er_sde (default) or euler; --guidance other than 1.0
    # turns CFG on, which is when --negative-prompt is used; --vae-tiling cuts the decode's memory
    sampling = sampling or {}
    # a continuous session reads its prompt from a file, which mflux reads again before each seed
    words = ["--prompt-file", str(prompt_file)] if prompt_file else ["--prompt", prompt]
    command = [str(RUNTIME / "bin" / "mflux-generate-krea2"), "--model", str(folder), *words]
    command += ["--width", str(width), "--height", str(height), "--seed", *(str(s) for s in (seeds or [seed])), "--steps", str(steps)]
    command += ["--output", str(out)]
    if sampling.get("scheduler") in ("er_sde", "euler"):
        command += ["--scheduler", sampling["scheduler"]]
    guidance = float(sampling.get("guidance", 1.0))
    if guidance != 1.0:
        command += ["--guidance", f"{guidance:g}"]
        if sampling.get("negative"):
            command += ["--negative-prompt", sampling["negative"]]
    for path, scale in pairs:
        command += ["--lora", path, f"{scale:g}"]
    if pairs and not sampling.get("bake", True):
        command.append("--no-bake-lora")
    if sampling.get("image"):
        # image-to-image: the picture to start from and its influence (0 none, mflux's default 0.4)
        source, strength = sampling["image"]
        command += ["--image", str(source), f"{float(strength):g}"]
    if settings:
        command += local_runner.mflux_memory_flags(settings)
        if settings.get("vaeTiling") and not settings["lowRam"]:
            command.append("--vae-tiling")
    return command


def _four_bit(build: str, folder: Path | None) -> bool:
    """A 4-bit model: the q4 build, or a checkpoint whose folder says so (e.g. silly-krea-2-mix-mlx-q4)."""
    if folder is not None:
        return bool(re.search(r"(^|[-_ ])(q4|4bit|4-bit|int4)($|[-_ ])", folder.name.lower()))
    return build == "mlx-q4"


SESSION_SEEDS = 500  # a continuous session's seeds; a new session starts when they run out


def run_continuous(
    prompt_file: Path,
    staging: Path,
    on_picture,
    width: int = 1024,
    height: int = 1024,
    steps: int | None = None,
    stack: list | None = None,
    memory: str = "auto",
    report=lambda *_: None,
    cancelled=lambda: False,
    folder: Path | None = None,
    sampling: dict | None = None,
    on_begin=None,
) -> int:
    """A continuous session: one run of mflux over many random seeds, so Krea 2 (or the checkpoint) and its LoRAs are
    loaded once and stay in memory between pictures. The prompt is read from prompt_file before each seed (mflux's
    --prompt-file), so it can be changed between pictures; each picture, once written, goes to on_picture(seed, path)
    as it is made. Ends when cancelled or when the seeds run out; returns how many pictures were made."""
    from PIL import Image

    from . import local_runner, loras

    state = policy()
    if folder is not None:
        if not state["licenceAccepted"]:
            raise RuntimeError("A Krea 2 checkpoint runs once the Krea 2 Community License Agreement is accepted on the Krea 2 card")
        if not (RUNTIME / "bin" / "mflux-generate-krea2").is_file():
            raise RuntimeError("Install Krea 2 once from its card: that sets up mflux, which runs Krea 2 checkpoints")
        state = {**state, "build": "mlx-q8"}
    elif not state["ready"]:
        raise RuntimeError(f"Krea 2 cannot run: {state['reason']}")
    if BUILDS[state["build"]]["platform"] != "macos-arm64" and folder is None:
        raise RuntimeError("A continuous session keeps the model loaded through mflux, on Apple silicon")
    refusal = prompt_refusal(prompt_file.read_text(encoding="utf-8"))
    if refusal:
        raise ValueError(refusal)
    width, height = max(256, int(width) // 16 * 16), max(256, int(height) // 16 * 16)
    steps = int(steps or STEPS)
    size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder else BUILDS[state["build"]]["size"]
    settings = local_runner.plan(int(size), memory)
    pairs = loras.resolve(stack, "krea-2")
    sampling = {**(sampling or {})}
    sampling.setdefault("bake", not (settings["lowRam"] or _four_bit(state["build"], folder)))
    seeds = [int.from_bytes(os.urandom(4), "little") for _ in range(SESSION_SEEDS)]
    # the session's own folder: every picture mflux writes in it is this session's, whatever mflux names it
    folder_out = staging / f"session-{os.getpid()}-{int(time.time() * 1000)}"
    folder_out.mkdir(parents=True, exist_ok=True)
    pattern = folder_out / "{seed}.png"
    label = f"Krea 2 checkpoint {folder.name}" if folder else "Krea 2"
    command = _command(state["build"], "", pattern, width, height, seeds[0], steps, pairs, settings, folder, seeds, sampling, prompt_file)
    taken = {"next": 0, "ended": False, "seen": set(), "last": {}}

    def collect(force: bool = False) -> None:
        # Any picture in the session's folder not yet taken, by what it is (its name, time and size), not by the name
        # it was expected to have: mflux may name a picture otherwise than by its seed, or write the same name again.
        # Whole: once mflux has begun the next picture (force), once the process has ended, or, between, once it has
        # stayed the same across two looks and reads as a picture. Its seed from its name when it holds one of ours,
        # else the next in order. (Until 2.1.10 a picture was looked for by its seed's name alone between those
        # moments, and one named otherwise waited for the next picture's first step, a step of Krea 2 later.)
        whole = force or taken["ended"]
        found = []
        for path in folder_out.glob("*.png"):
            try:
                stat = path.stat()
            except OSError:
                continue
            mark = (path.name, stat.st_mtime_ns, stat.st_size)
            if mark in taken["seen"] or stat.st_size == 0:
                continue
            if not whole and taken["last"].get(path.name) != mark:
                taken["last"][path.name] = mark  # seen once: taken if the same next time
                continue
            found.append((stat.st_mtime_ns, path, mark))
        for _, path, mark in sorted(found):
            try:
                with Image.open(path) as picture:
                    picture.verify()
            except (OSError, SyntaxError):
                continue
            taken["seen"].add(mark)
            by_name = next((s for s in seeds if str(s) in path.stem), None)
            seed = by_name if by_name is not None else seeds[min(taken["next"], len(seeds) - 1)]
            on_picture(seed, path)
            taken["next"] += 1

    def begun() -> None:
        collect(force=True)  # the picture before is written: taken before this one goes on
        if on_begin is not None:
            on_begin()

    if on_begin is not None:
        on_begin()  # the first picture begins with the process
    try:
        local_runner.run(
            command,
            steps,
            report,
            cancelled,
            label,
            images=len(seeds),
            on_tick=collect,
            continuous=True,
            on_next=begun,
        )
    except InterruptedError:
        taken["ended"] = True
        collect()
        raise
    finally:
        taken["ended"] = True
        collect()
        import shutil

        shutil.rmtree(folder_out, ignore_errors=True)
    return taken["next"]


def generate_to_file(prompt: str, path: Path, width: int = 1024, height: int = 1024, seed: int | None = None, **options) -> dict:
    """One picture (generate_many with one seed); a picture the filter withholds is refused."""
    [result] = generate_many(prompt, [path], [seed], width, height, **options)
    if result.get("withheld"):
        raise ValueError(f"The content filter withheld this picture (NSFW score {result['nsfw']:.2f}).")
    return result


def generate_many(
    prompt: str,
    paths: list[Path],
    seeds: list[int | None],
    width: int = 1024,
    height: int = 1024,
    steps: int | None = None,
    stack: list | None = None,
    memory: str = "auto",
    report=lambda *_: None,
    cancelled=lambda: False,
    folder: Path | None = None,
    sampling: dict | None = None,
    **_options,
) -> list[dict]:
    """Pictures from Krea 2 or a Krea 2 checkpoint, every seed in one run of mflux (the model loaded once), each
    through the content filter: a withheld one is deleted and reported as withheld, the rest returned. The licence's
    notice goes with each; without the filter, the warning."""
    from PIL import Image

    from . import content_filter, local_runner, loras

    state = policy()
    if folder is not None:
        # a checkpoint of the person's own (checkpoints.py): Krea 2's licence and mflux, not a pinned build
        if not state["licenceAccepted"]:
            raise RuntimeError("A Krea 2 checkpoint runs once the Krea 2 Community License Agreement is accepted on the Krea 2 card")
        if not (RUNTIME / "bin" / "mflux-generate-krea2").is_file():
            raise RuntimeError("Install Krea 2 once from its card: that sets up mflux, which runs Krea 2 checkpoints")
        state = {**state, "build": "mlx-q8"}
    elif not state["ready"]:
        raise RuntimeError(f"Krea 2 cannot run: {state['reason']}")
    refusal = prompt_refusal(prompt)
    if refusal:
        raise ValueError(refusal)
    started = time.time()
    first = int.from_bytes(os.urandom(4), "little")
    seeds = [int(s) if s is not None else (first + i) & 0xFFFFFFFF for i, s in enumerate(seeds)]
    # Krea 2 works in multiples of 16
    width, height = max(256, int(width) // 16 * 16), max(256, int(height) // 16 * 16)
    steps = int(steps or STEPS)
    size = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder else BUILDS[state["build"]]["size"]
    settings = local_runner.plan(int(size), memory)
    pairs = loras.resolve(stack, "krea-2")
    sampling = {**(sampling or {})}
    # baking a LoRA into a 4-bit model turns the layers it touches to 8-bit: kept 4-bit, the LoRA applied as it runs,
    # when the model is 4-bit or memory is short
    sampling.setdefault("bake", not (settings["lowRam"] or _four_bit(state["build"], folder)))
    label = f"Krea 2 checkpoint {folder.name}" if folder else "Krea 2"
    pattern = paths[0].parent / f"{paths[0].stem}-{{seed}}.png"
    if BUILDS[state["build"]]["platform"] == "macos-arm64" or folder is not None:
        command = _command(state["build"], prompt, pattern, width, height, seeds[0], steps, pairs, settings, folder, seeds, sampling)
        local_runner.run(command, steps, report, cancelled, label, images=len(seeds))
        made = {seed: Path(str(pattern).replace("{seed}", str(seed))) for seed in seeds}
    else:
        made = {}
        for index, seed in enumerate(seeds):  # diffusers: one picture a run
            out = Path(str(pattern).replace("{seed}", str(seed)))
            share = lambda f, m=None, i=index: report((i + f) / len(seeds), m)  # noqa: E731
            local_runner.run(
                _command(state["build"], prompt, out, width, height, seed, steps, pairs, settings), steps, share, cancelled, label
            )
            made[seed] = out
    if not state["filterInstalled"]:
        _note_run_without_filter()
    results = []
    for seed, target in zip(seeds, paths, strict=True):
        produced = made[seed]
        if not produced.is_file():
            raise RuntimeError(f"{label} finished without the picture for seed {seed}")
        produced.replace(target)
        verdict = None
        if state["filterInstalled"]:
            import numpy as np

            verdict = content_filter.check(np.asarray(Image.open(target).convert("RGB")))
            if verdict["withheld"]:
                target.unlink(missing_ok=True)
                results.append({"withheld": True, "nsfw": verdict["nsfw"], "seed": seed})
                continue
        with Image.open(target) as picture:
            dims = picture.size
        results.append(
            {
                "path": str(target),
                "model": "krea-2",
                "provider": f"Krea 2 checkpoint {folder.name} (mflux)" if folder else BUILDS[state["build"]]["label"],
                "seconds": round((time.time() - started) / len(seeds), 1),
                "width": dims[0],
                "height": dims[1],
                "seed": seed,
                "memory": settings,
                "contentFilter": verdict or "removed",
                # the warning goes with pictures until it is acknowledged on the Krea 2 card, not after
                "warning": None if verdict or state.get("removalAcknowledged") else REMOVED_WARNING,
                "notice": NOTICE,
            }
        )
    return results


class ConsentBody(BaseModel):
    acceptLicence: bool = False


class InstallBody(BaseModel):
    build: str | None = None


@router.get("/terms")
def terms() -> dict:
    """What a person reads before installing: the licence's terms, the filter that comes with it, the warning shown if
    the filter is later removed, and the builds for this machine."""
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
        "removedWarning": REMOVED_WARNING,
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
        record_consent(body.acceptLicence)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return policy()


@router.post("/install", status_code=202)
def start_install(body: InstallBody) -> dict:
    build = body.build or recommended()
    if build not in builds_here():
        raise HTTPException(400, f"no Krea 2 build for this machine ({machine()})")
    if not consent().get("licence"):
        raise HTTPException(409, "accept the licence first")
    return jobs.submit("krea-2-install", lambda _id, report, cancelled: install(build, report, cancelled))


@router.post("/filter", status_code=202)
def reinstall_filter() -> dict:
    """Put the content filter back after it was removed: the classifier fetched again, checked against its pins."""
    from .model_manager import download

    return jobs.submit("model-download", lambda _id, report, cancelled: download(FILTER["id"], report, cancelled))


@router.post("/acknowledge-removal")
def acknowledge() -> dict:
    """The person has read the warning about the removed filter; recorded with the wording's hash."""
    return acknowledge_removal()
