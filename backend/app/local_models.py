"""Local generative model slots.

A slot is a declaration in models/local_models.json under the data directory:
what it makes (image or video), a name, and the runner that makes it. Two
runners exist: "onnx-diffusion", which runs a diffusers-layout ONNX folder
through local_diffusion in the engine's own ONNX Runtime, and "command", which
runs any program the person installs (a venv script, a binary, a container
entry point) with the prompt and an output path substituted into its argument
template, then ingests the file it wrote. The second is what makes the slots
modular: a new image or video model is a folder of weights plus a runner
script plus one entry here, never a change to the engine. A diffusion folder
with no declaration is still offered, as an undeclared image slot, so the
simplest case needs no file at all.

{
  "slots": [
    {"id": "sd-turbo", "kind": "image", "runner": "onnx-diffusion", "folder": "sd-turbo",
     "label": "SD Turbo (local)", "steps": 1, "guidance": 0.0, "licence": "Stability non-commercial"},
    {"id": "ltx-2", "kind": "video", "runner": "command",
     "command": ["/path/to/venv/bin/python", "/path/to/run_ltx.py", "--prompt", "{prompt}", "--seconds", "{seconds}",
                 "--width", "{width}", "--height", "{height}", "--seed", "{seed}", "--out", "{out}"],
     "extension": ".mp4", "label": "LTX-2 (local)", "sizes": ["1280x720", "720x1280"], "seconds": 5}
  ]
}
"""

import json
import shlex
import subprocess
import time
from pathlib import Path

from .paths import DATA_DIR
from .processes import communicate

REGISTRY = DATA_DIR / "models" / "local_models.json"
RUNNERS = ("onnx-diffusion", "command")
KINDS = ("image", "video")


def declared() -> list[dict]:
    """The slots the registry declares, each checked to its runner's needs; a bad one is listed with its reason."""
    if not REGISTRY.is_file():
        return []
    try:
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        reason = f"the registry is not JSON: {exc}"
        return [{"id": "local_models.json", "kind": "image", "runner": "none", "ready": False, "reason": reason}]
    out = []
    for raw in data.get("slots") or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        slot = {
            "id": str(raw["id"]),
            "label": str(raw.get("label") or raw["id"]),
            "kind": raw.get("kind") if raw.get("kind") in KINDS else "image",
            "runner": raw.get("runner") if raw.get("runner") in RUNNERS else "none",
            "licence": raw.get("licence"),
            "sizes": [str(s) for s in (raw.get("sizes") or [])],
            "seconds": raw.get("seconds"),
            "steps": raw.get("steps"),
            "guidance": raw.get("guidance"),
            "folder": raw.get("folder"),
            "command": raw.get("command"),
            "extension": raw.get("extension"),
            "ready": False,
            "reason": None,
        }
        if slot["runner"] == "onnx-diffusion":
            from .local_diffusion import MODELS, PARTS

            folder = MODELS / str(slot["folder"] or slot["id"])
            missing = [part for part in PARTS if not (folder / part).is_file()]
            slot["ready"] = not missing
            slot["reason"] = None if not missing else f"missing {missing[0]} under {folder}"
        elif slot["runner"] == "command":
            command = slot["command"]
            if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
                slot["reason"] = "command must be a list of strings"
            elif "{out}" not in " ".join(command):
                slot["reason"] = "command must name {out}, the file it writes"
            elif not Path(command[0]).is_file() and not _on_path(command[0]):
                slot["reason"] = f"{command[0]} is not an executable on this machine"
            else:
                slot["ready"] = True
        else:
            slot["reason"] = f"runner must be one of {', '.join(RUNNERS)}"
        out.append(slot)
    return out


def _on_path(program: str) -> bool:
    from shutil import which

    return which(program) is not None


def catalogue_entries() -> list[dict]:
    """Every local slot as the generator catalogue shows it: declared ones first, then undeclared diffusion folders."""
    from .local_diffusion import installed

    entries = []
    seen_folders = set()
    for slot in declared():
        if slot["runner"] == "onnx-diffusion":
            seen_folders.add(str(slot["folder"] or slot["id"]))
        options = {}
        if slot["kind"] == "image":
            steps = slot["steps"] if slot["steps"] is not None else 4
            guidance = slot["guidance"] if slot["guidance"] is not None else 0.0
            options = {"steps": steps, "guidance": guidance}
        else:
            options = {"seconds": slot["seconds"] if slot["seconds"] is not None else 5}
        sizes = slot["sizes"] or (["512x512", "768x512", "512x768"] if slot["kind"] == "image" else ["1280x720", "720x1280"])
        entries.append(
            {
                "id": f"local:{slot['id']}",
                "label": f"{slot['label']} (local)" if "(local)" not in slot["label"] else slot["label"],
                "kind": slot["kind"],
                "provider": "local",
                "providerLabel": "This computer",
                "sizes": sizes,
                "options": options,
                "ready": slot["ready"],
                "reason": slot["reason"],
                "runner": slot["runner"],
                "licence": slot["licence"],
            }
        )
    krea = krea2_slot()
    if krea is not None:
        entries.append(
            {
                "id": "local:krea-2",
                "label": "Krea 2 Turbo (local)",
                "kind": "image",
                "provider": "local",
                "providerLabel": "This computer",
                "sizes": krea["sizes"],
                "options": {
                    "steps": krea["steps"],
                    "guidance": krea["guidance"],
                    "loras": "krea-2",
                    "memory": "auto",
                    "scheduler": "er_sde",
                    "image": 0.4,
                    "continuous": True,
                },
                "ready": krea["ready"],
                "reason": krea["reason"],
                "runner": "krea-2",
                "licence": krea["licence"],
            }
        )
    for slot in klein_slots():
        entries.append(
            {
                "id": f"local:{slot['id']}",
                "label": f"{slot['label']} (local)",
                "kind": "image",
                "provider": "local",
                "providerLabel": "This computer",
                "sizes": slot["sizes"],
                "options": {"steps": slot["steps"], "guidance": 1.0, "loras": slot["id"], "memory": "auto"},
                "ready": slot["ready"],
                "reason": slot["reason"],
                "runner": "mflux-klein",
                "licence": slot["licence"],
            }
        )
    for slot in checkpoint_slots():
        entries.append(
            {
                "id": f"local:{slot['id']}",
                "label": slot["label"],
                "kind": "image",
                "provider": "local",
                "providerLabel": "This computer",
                "sizes": slot["sizes"],
                "options": {
                    "steps": slot["steps"],
                    "guidance": 1.0,
                    "loras": slot["base"],
                    "memory": "auto",
                    **({"scheduler": "er_sde", "image": 0.4, "continuous": True} if slot["runner"] == "krea-2" else {}),
                },
                "ready": slot["ready"],
                "reason": slot["reason"],
                "runner": slot["runner"],
                "licence": slot["licence"],
            }
        )
    for model in installed():
        if model["id"] in seen_folders:
            continue
        entries.append(
            {
                "id": f"local:{model['id']}",
                "label": f"{model['id']} (local)",
                "kind": "image",
                "provider": "local",
                "providerLabel": "This computer",
                "sizes": ["512x512", "768x512", "512x768"],
                "options": {"steps": 4, "guidance": 0.0},
                "ready": bool(model["complete"]),
                "reason": None if model["complete"] else "the folder is missing a part",
                "runner": "onnx-diffusion",
                "licence": model.get("licence"),
            }
        )
    return entries


def krea2_slot() -> dict | None:
    """Krea 2, once its licence has been accepted: offered in the generator with its readiness and reason."""
    from . import krea2

    state = krea2.policy()
    if not state["licenceAccepted"]:
        return None
    blank = {"seconds": None, "extension": None, "command": None, "folder": None}
    return {
        "id": "krea-2",
        "label": "Krea 2 Turbo",
        "kind": "image",
        "runner": "krea-2",
        "licence": f"{krea2.LICENCE_NAME} ({krea2.LICENCE_VERSION})",
        "sizes": ["1024x1024", "1344x768", "768x1344", "1536x1024", "1024x1536"],
        "steps": krea2.STEPS,
        "guidance": 1.0,
        "ready": state["ready"],
        "reason": state["reason"],
        **blank,
    }


def klein_slots() -> list[dict]:
    """FLUX.2 [klein] 4B and 9B, each once its licence has been accepted, with its readiness and reason."""
    from . import klein

    out = []
    for variant, spec in klein.VARIANTS.items():
        state = klein.policy(variant)
        if not state["licenceAccepted"]:
            continue
        blank = {"seconds": None, "extension": None, "command": None, "folder": None, "guidance": 1.0}
        out.append(
            {
                "id": variant,
                "label": spec["label"],
                "kind": "image",
                "runner": "mflux-klein",
                "licence": spec["licence"]["name"],
                "sizes": klein.SIZES,
                "steps": klein.STEPS,
                "ready": state["ready"],
                "reason": state["reason"],
                **blank,
            }
        )
    return out


def checkpoint_slots() -> list[dict]:
    """The person's own checkpoints (models/checkpoints/<model>/<name>/), each as a model of its own."""
    from . import checkpoints, klein, krea2

    out = []
    krea_state = krea2.policy()
    mflux_krea = (krea2.RUNTIME / "bin" / "mflux-generate-krea2").is_file()
    for entry in checkpoints.entries():
        reason = entry["problem"]
        if entry["base"] == "krea-2":
            runner, sizes, steps, licence = (
                "krea-2",
                ["1024x1024", "1344x768", "768x1344", "1536x1024", "1024x1536"],
                krea2.STEPS,
                krea2.LICENCE_NAME,
            )
            reason = reason or (
                None if krea_state["licenceAccepted"] else "accept the Krea 2 licence on its card first (a Krea 2 checkpoint is under it)"
            )
            reason = reason or (None if mflux_krea else "install Krea 2 once from its card: that sets up mflux")
        else:
            runner, sizes, steps, licence = "mflux-klein", klein.SIZES, klein.STEPS, "the checkpoint's own licence"
            reason = reason or (None if klein._is_apple_silicon() else "Klein checkpoints run on Apple silicon (mflux)")
            reason = reason or (
                None if klein._cli().is_file() else "install FLUX.2 [klein] 4B or Krea 2 once from its card: that sets up mflux"
            )
        out.append(
            {
                "id": entry["id"],
                "label": f"{entry['name']} ({entry['baseLabel']} checkpoint, local)",
                "kind": "image",
                "runner": runner,
                "base": entry["base"],
                "checkpoint": entry["folder"],
                "licence": licence,
                "sizes": sizes,
                "steps": steps,
                "guidance": 1.0,
                "ready": reason is None,
                "reason": reason,
                "seconds": None,
                "extension": None,
                "command": None,
                "folder": None,
            }
        )
    return out


def resolve(name: str) -> dict | None:
    """The slot behind local:<name>: a declared one, or an undeclared diffusion folder of that name."""
    if name == "krea-2":
        return krea2_slot()
    if name.startswith("ckpt:"):
        return next((slot for slot in checkpoint_slots() if slot["id"] == name), None)
    if name.startswith("flux2-klein-"):
        return next((slot for slot in klein_slots() if slot["id"] == name), None)
    for slot in declared():
        if slot["id"] == name:
            return slot
    from .local_diffusion import MODELS

    if (MODELS / name).is_dir() and "/" not in name and ".." not in name:
        blank = {"steps": None, "guidance": None, "seconds": None, "extension": None, "command": None}
        return {"id": name, "kind": "image", "runner": "onnx-diffusion", "folder": name, "ready": True, "reason": None, **blank}
    return None


def run_command_slot(
    slot: dict, prompt: str, out: Path, width: int, height: int, seconds: float, seed: int | None, report, cancelled
) -> dict:
    """Run a command slot with its template filled; the file at {out} is the result."""
    filled = []
    values = {
        "prompt": prompt,
        "out": str(out),
        "width": str(width),
        "height": str(height),
        "seconds": str(seconds),
        "seed": str(seed if seed is not None else 0),
    }
    for part in slot["command"]:
        text = part
        for key, value in values.items():
            text = text.replace("{" + key + "}", value)
        filled.append(text)
    started = time.time()
    report(0.05)
    process = subprocess.Popen(filled, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = communicate(process, cancelled=cancelled)
    if process.returncode:
        tail = (error or output).decode(errors="replace")[-600:]
        raise ValueError(f"{shlex.join(filled[:1])} failed ({process.returncode}): {tail}")
    if not out.is_file() or out.stat().st_size == 0:
        raise ValueError(f"the runner finished but wrote nothing at {out}")
    report(1.0)
    return {"path": str(out), "model": slot["id"], "provider": "command", "seconds": round(time.time() - started, 1)}
