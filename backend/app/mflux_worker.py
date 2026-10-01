"""formcut's Krea 2 worker for prompt wraps (2.3.3), run with the Python of formcut's mflux environment.

    <runtime>/bin/python mflux_worker.py <plan.json>

The owner's prompt wrap stalled at "loading the model" and took the browser down: a wrap whose entries differ in their
LoRAs, size or steps started mflux again for every change, a full load of the model each time, and a wrap with a LoRA
taking turns changes at every entry (31 loads a round for 31 prompts). This loads the model, and every LoRA the wrap
uses, once, the way mflux-generate-krea2 does (its own argument parser, Krea2(...), its callbacks, from the same
arguments formcut gives the command, so memory, tiling and a checkpoint folder behave the same), then makes each picture
of the plan with mflux's own Krea2.generate_image, which takes the prompt, seed, size, steps, sampler and CFG per call.
The LoRAs are applied unbaked: each layer's scale is set to the entry's scale for its file, and the LoRAs an entry does
not use are set aside from their layers for that picture, so they cost it nothing.

The plan (JSON): {"argv": [the command's arguments, without the command], "loras": [absolute paths],
"jobs": [{"prompt", "seed", "steps", "width", "height", "guidance", "negative", "scheduler", "scales": {path: scale},
"output"}]}. Each picture is written to its job's output; mflux's own progress bar is printed as it goes.

This file imports only mflux and mlx: formcut's engine is not on its path.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def tag_layers(loader_cls, layer_classes, known: list[str]):
    """While the model loads, each LoRA layer made is marked with the file it came from: mflux applies one file at a
    time through LoRALoader._apply_single_lora(transformer, lora_file, ...)."""
    current = {"file": None}
    known_resolved = {str(Path(p).resolve()): p for p in known}
    original = loader_cls._apply_single_lora

    def applying(transformer, lora_file, *args, **kwargs):
        current["file"] = known_resolved.get(str(Path(lora_file).resolve()), str(lora_file))
        try:
            return original(transformer, lora_file, *args, **kwargs)
        finally:
            current["file"] = None

    loader_cls._apply_single_lora = staticmethod(applying)
    for cls in layer_classes:
        made = cls.__init__

        def init(self, *args, _made=made, **kwargs):
            _made(self, *args, **kwargs)
            object.__setattr__(self, "_formcut_file", current["file"])

        cls.__init__ = init
    return current


def find_layers(root, layer_classes, fused_cls=None):
    """Every LoRA layer under root, and every layer stacking several. An mlx module is a dict of its children (modules,
    and lists or dicts of them), so walking dicts, lists and tuples finds them all."""
    layers, stacks, seen = [], [], set()

    def walk(value):
        if id(value) in seen:
            return
        seen.add(id(value))
        if isinstance(value, tuple(layer_classes)):
            layers.append(value)
        if fused_cls is not None and isinstance(value, fused_cls):
            stacks.append(value)
            object.__setattr__(value, "_formcut_all", list(value.loras))
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                walk(child)

    walk(root)
    return layers, stacks


def set_scales(layers, stacks, scales: dict) -> int:
    """Each LoRA layer at its file's scale for this picture; the files not in it set aside from the layers stacking
    several (and at 0 where a layer holds one alone). Returns how many layers are active."""
    active = 0
    for layer in layers:
        scale = float(scales.get(getattr(layer, "_formcut_file", None), 0.0))
        layer.scale = scale
        active += scale != 0.0
    for stack in stacks:
        stack.loras = [
            lora
            for lora in getattr(stack, "_formcut_all", stack.loras)
            if float(scales.get(getattr(lora, "_formcut_file", None), 0.0)) != 0.0
        ]
    return active


def main() -> int:
    plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))

    from mflux.callbacks.callback_manager import CallbackManager
    from mflux.cli.parser.parsers import lora_init_kwargs_from_args
    from mflux.models.common.lora.layer.fused_linear_lora_layer import FusedLoRALinear
    from mflux.models.common.lora.layer.linear_lokr_layer import LoKrLinear
    from mflux.models.common.lora.layer.linear_lora_layer import LoRALinear
    from mflux.models.common.lora.mapping.lora_loader import LoRALoader
    from mflux.models.common.resolution.config_resolution import ConfigResolution
    from mflux.models.krea2.cli.krea2_generate import build_parser
    from mflux.models.krea2.latent_creator import Krea2LatentCreator
    from mflux.models.krea2.variants.txt2img.krea2 import Krea2

    tag_layers(LoRALoader, (LoRALinear, LoKrLinear), plan["loras"])
    args = build_parser().parse_args(plan["argv"])
    model = Krea2(
        model_config=ConfigResolution.resolve_restricted(args.model, "krea-2", model_path=args.model_path),
        quantize=args.quantize,
        model_path=args.model_path,
        **lora_init_kwargs_from_args(args),
    )
    memory_saver = CallbackManager.register_callbacks(args=args, model=model, latent_creator=Krea2LatentCreator)
    layers, stacks = find_layers(model.transformer, (LoRALinear, LoKrLinear), FusedLoRALinear)
    untagged = sum(getattr(layer, "_formcut_file", None) is None for layer in layers)
    print(
        f"formcut worker: the model loaded once, {len(layers)} LoRA layers from {len(plan['loras'])} files ({untagged} unmarked)",
        flush=True,
    )
    try:
        for job in plan["jobs"]:
            set_scales(layers, stacks, job.get("scales") or {})
            image = model.generate_image(
                seed=int(job["seed"]),
                prompt=job["prompt"],
                num_inference_steps=int(job["steps"]),
                height=int(job["height"]),
                width=int(job["width"]),
                guidance=float(job.get("guidance") or 1.0),
                scheduler=job.get("scheduler") or args.scheduler,
                negative_prompt=job.get("negative") or None,
            )
            image.save(path=job["output"], export_json_metadata=False)
            print(f"formcut worker: wrote {Path(job['output']).name}", flush=True)
    finally:
        if memory_saver:
            print(memory_saver.memory_stats())
    return 0


if __name__ == "__main__":
    sys.exit(main())
