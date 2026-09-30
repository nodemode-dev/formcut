"""A LoRA checked against mflux's own key mapping, and renamed where that makes it apply (v2.2.9).

The owner: several OneTrainer and Civitai LoRAs did not work with mflux. mflux matches a LoRA's keys to its model by
exact patterns (krea2_lora_mapping.py, flux2_lora_mapping.py); a key it does not know is skipped with a warning, and a
file none of whose keys it knows stops the run ("No LoRA layers were applied"). Some trainers name the same weights
otherwise: OneTrainer's historical ("mixture") layout puts a DiT's weights under lora_transformer_ where mflux looks
for lora_unet_; LyCORIS writes lycoris_ and flat LoKr names that mflux's Krea 2 mapping knows only dotted; ComfyUI
exports may carry model.diffusion_model. Others hold what mflux does not load at all: text-encoder weights, a DoRA's
magnitude, LoHa (hada_) factors, full weight differences.

The audit runs in the mflux environment formcut installed (models/krea-2/runtime), against the installed mflux's own
patterns (its mlx left unloaded: the mapping is plain data), so it is right for whichever mflux is there. For each file:
how many keys apply as they are, which renames make more apply (tried in turn: the prefix swaps above, then a flat
name matched to the mapping's dotted module path), and what is left, by kind. formcut then writes a copy with the
renames (the header rewritten, the tensors' bytes as they were) beside the library, and gives mflux that copy.
"""

from __future__ import annotations

import json
import os
import struct
import subprocess
from pathlib import Path

SCRIPT = r'''
import importlib.util, json, os, re, struct, sys, types

# mflux's two mapping modules loaded from their files, not through mflux's package, which imports the whole model
# (transformers, the weights code): the mapping is plain data. mlx is used where it is (the Mac); elsewhere a
# stand-in carries its names, as nothing here computes.
try:
    import mlx.core  # noqa: F401
except ImportError:
    import importlib.machinery

    class _Stub(types.ModuleType):
        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return type(name, (), {"__init__": lambda self, *a, **k: None})

    for _name in ("mlx", "mlx.core", "mlx.nn"):
        _module = _Stub(_name)
        _module.__spec__ = importlib.machinery.ModuleSpec(_name, None)
        sys.modules[_name] = _module
    sys.modules["mlx"].core, sys.modules["mlx"].nn = sys.modules["mlx.core"], sys.modules["mlx.nn"]

ROOT = list(importlib.util.find_spec("mflux").submodule_search_locations)[0]

def load(dotted, relative):
    if dotted in sys.modules:
        return sys.modules[dotted]
    spec = importlib.util.spec_from_file_location(dotted, os.path.join(ROOT, relative))
    module = importlib.util.module_from_spec(spec)
    sys.modules[dotted] = module
    spec.loader.exec_module(module)
    return module

def patterns_of(targets):
    """The source patterns mflux's LoRALoader._build_pattern_mappings makes of a mapping's targets."""
    out = []
    for target in targets:
        out += list(target.possible_up_patterns) + list(target.possible_down_patterns) + list(target.possible_alpha_patterns)
        for full, factors, extra in (("lokr_w1", ("lokr_w1_a", "lokr_w1_b"), None), ("lokr_w2", ("lokr_w2_a", "lokr_w2_b"), "lokr_t2")):
            for pattern in getattr(target, f"possible_{full}_patterns"):
                out.append(pattern)
                if pattern.endswith("." + full):
                    base = pattern[: -len(full) - 1]
                    out += [f"{base}.{name}" for name in factors] + ([f"{base}.{extra}"] if extra else [])
        out += list(target.possible_dora_scale_patterns)
    return out

def mapping(model):
    load("mflux.models.common.lora.mapping.lora_mapping", "models/common/lora/mapping/lora_mapping.py")
    if model == "krea-2":
        M = load("mflux.models.krea2.weights.krea2_lora_mapping", "models/krea2/weights/krea2_lora_mapping.py").Krea2LoRAMapping
    else:
        load("mflux.models.common.lora.mapping.lora_transforms", "models/common/lora/mapping/lora_transforms.py")
        M = load("mflux.models.flux2.weights.flux2_lora_mapping", "models/flux2/weights/flux2_lora_mapping.py").Flux2LoRAMapping
    patterns = patterns_of(M.get_mapping())
    exact = {p for p in patterns if "{block}" not in p}
    templated = {p for p in patterns if "{block}" in p}
    return patterns, exact, templated

SUFFIXES = sorted([
    "lora_A.weight", "lora_B.weight", "lora_down.weight", "lora_up.weight", "lora.down.weight", "lora.up.weight",
    "lora_A.default.weight", "lora_B.default.weight", "lora_down.default.weight", "lora_up.default.weight",
    "alpha", "lokr_w1", "lokr_w2", "lokr_w1_a", "lokr_w1_b", "lokr_w2_a", "lokr_w2_b", "lokr_t2", "dora_scale",
], key=len, reverse=True)
PREFIXES = ("", "transformer.", "diffusion_model.", "base_model.model.")
FLAT = ("lora_unet_", "lora_transformer_", "lycoris_")
SWAPS = (("lora_transformer_", "lora_unet_"), ("lycoris_", "lora_unet_"), ("model.diffusion_model.", "diffusion_model."),
         ("base_model.model.transformer.", "transformer."), ("unet.", ""))

def fits(key, exact, templated):
    for candidate in (key, key + ".weight"):
        if candidate in exact:
            return True
        for found in re.finditer(r"\d+", candidate):
            if candidate[: found.start()] + "{block}" + candidate[found.end():] in templated:
                return True
    return False

def split(key):
    for suffix in SUFFIXES:
        if key.endswith("." + suffix):
            return key[: -len(suffix) - 1], suffix
    return None, None

def dotted_index(patterns):
    """Each dotted module path in the mapping (no prefix), by its flat spelling: to read a flat name dotted."""
    index = {}
    for pattern in patterns:
        if any(pattern.startswith(p) for p in ("transformer.", "diffusion_model.", "base_model.", "lora_unet_", "lycoris_")):
            continue
        body, suffix = split(pattern)
        if body:
            index.setdefault(body.replace(".", "_"), body)
    return index

def audit(path, model, cache={}):
    if model not in cache:
        patterns, exact, templated = mapping(model)
        cache[model] = (exact, templated, dotted_index(patterns))
    exact, templated, index = cache[model]
    with open(path, "rb") as handle:
        (length,) = struct.unpack("<Q", handle.read(8))
        header = json.loads(handle.read(length))
    keys = [k for k in header if k != "__metadata__"]
    matched, renames, left, sample = 0, {}, {"te": 0, "dora": 0, "loha": 0, "diff": 0, "other": 0}, []
    for key in keys:
        if fits(key, exact, templated):
            matched += 1
            continue
        found = None
        for old, new in SWAPS:
            if key.startswith(old) and fits(new + key[len(old):], exact, templated):
                found = new + key[len(old):]
                break
        if found is None and key.startswith(FLAT):
            flat_prefix = next(p for p in FLAT if key.startswith(p))
            body, suffix = split(key)
            if body:
                flat = body[len(flat_prefix):]
                readings = [flat] if flat in index else []
                for number in re.finditer(r"\d+", flat):
                    form = flat[: number.start()] + "{block}" + flat[number.end():]
                    if form in index:
                        readings.append(index[form].replace("{block}", number.group(0)))
                readings = [index[r] if r in index else r for r in readings]
                for dotted in readings:
                    for prefix in PREFIXES:
                        candidate = f"{prefix}{dotted}.{suffix}"
                        if fits(candidate, exact, templated):
                            found = candidate
                            break
                    if found:
                        break
        if found is not None:
            renames[key] = found
            matched += 1
            continue
        low = key.lower()
        if low.startswith(("lora_te", "text_encoder", "te1", "te2", "text_encoders.", "cond_stage_model", "lora_te1_", "lora_te2_")):
            left["te"] += 1
        elif "dora_scale" in low or "magnitude" in low:
            left["dora"] += 1
        elif "hada_" in low:
            left["loha"] += 1
        elif low.endswith((".diff", ".diff_b")):
            left["diff"] += 1
        else:
            left["other"] += 1
            if len(sample) < 5:
                sample.append(key)
    return {"keys": len(keys), "matched": matched, "renames": renames, "left": left, "sample": sample}

jobs = json.load(sys.stdin)
out = {}
for job in jobs:
    try:
        out[job["path"]] = audit(job["path"], job["model"])
    except Exception as exc:
        out[job["path"]] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
print(json.dumps(out))
'''


def mflux_version(python: Path) -> str:
    try:
        done = subprocess.run(
            [str(python), "-c", "import importlib.metadata as m; print(m.version('mflux'))"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return done.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def run(python: Path, jobs: list[dict]) -> dict:
    """The audit of each {path, model} job, from the mflux environment's own Python."""
    if not jobs:
        return {}
    done = subprocess.run([str(python), "-c", SCRIPT], input=json.dumps(jobs), capture_output=True, text=True, timeout=300, check=False)
    if done.returncode != 0:
        raise RuntimeError(
            (done.stderr or done.stdout).strip().splitlines()[-1][:300] if (done.stderr or done.stdout).strip() else "the audit failed"
        )
    return json.loads(done.stdout.strip().splitlines()[-1])


def summary(result: dict, model_label: str) -> tuple[bool, str]:
    """Whether the LoRA can be used, and what to say about it."""
    if "error" in result:
        return True, f"not checked ({result['error']})"
    keys, matched, left = result["keys"], result["matched"], result["left"]
    parts = []
    if result["renames"]:
        parts.append(f"{len(result['renames'])} keys renamed to the names mflux reads")
    if left["te"]:
        parts.append(f"{left['te']} text-encoder keys not used (mflux applies LoRAs to the image model)")
    if left["dora"]:
        parts.append("its DoRA magnitude is not applied by mflux, only its LoRA part: it will not look as trained")
    if left["loha"]:
        parts.append(f"{left['loha']} LoHa keys, a kind mflux does not load")
    if left["diff"]:
        parts.append(f"{left['diff']} full-weight differences, which mflux does not load")
    if left["other"]:
        parts.append(f"{left['other']} keys that fit nothing in {model_label} (for instance {result['sample'][0]})")
    if matched == 0:
        why = (
            "it is a LoHa, which mflux does not load"
            if left["loha"]
            else "it holds only text-encoder weights"
            if left["te"] and not left["other"]
            else f"none of its {keys} keys fit {model_label}: it was made for another model, or in a layout mflux does not read"
        )
        return False, why
    head = f"{matched} of {keys} keys apply" if matched < keys else f"all {keys} keys apply"
    return True, "; ".join([head, *parts])


def rewrite(source: Path, target: Path, renames: dict) -> Path:
    """A copy with keys renamed: the header rewritten, every tensor's bytes and offsets as they were."""
    with open(source, "rb") as handle:
        (length,) = struct.unpack("<Q", handle.read(8))
        header = json.loads(handle.read(length))
        renamed = {renames.get(key, key): value for key, value in header.items()}
        text = json.dumps(renamed, separators=(",", ":")).encode("utf-8")
        text += b" " * (-len(text) % 8)  # the header padded to eight bytes, as the format asks
        target.parent.mkdir(parents=True, exist_ok=True)
        staged = target.with_name(f".{target.name}.{os.getpid()}.part")
        with open(staged, "wb") as out:
            out.write(struct.pack("<Q", len(text)))
            out.write(text)
            while chunk := handle.read(8 << 20):
                out.write(chunk)
    os.replace(staged, target)
    return target
