"""The Krea 2 worker for prompt wraps (2.3.3): the model and every LoRA the wrap uses loaded once, each picture with its
own settings and LoRA scales. Its logic is checked here with stand-ins shaped as mflux's own (an mlx module is a dict of
its children; LoRALoader applies one file at a time; a stacking layer keeps its LoRAs in .loras, each with a .scale)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

WORKER = Path(__file__).resolve().parents[1] / "backend" / "app" / "mflux_worker.py"
spec = importlib.util.spec_from_file_location("mflux_worker", WORKER)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


class Module(dict):
    """An mlx module, as far as the walk sees one: a dict of its children."""

    def __setattr__(self, name, value):
        if isinstance(value, (dict, list, tuple)):
            self[name] = value
        else:
            object.__setattr__(self, name, value)

    def __getattr__(self, name):  # as mlx's Module reads its children
        if name in self:
            return self[name]
        raise AttributeError(name)


class LoRALinear(Module):
    def __init__(self, scale=1.0):
        super().__init__()
        self.scale = scale


class LoKrLinear(LoRALinear):
    pass


class FusedLoRALinear(Module):
    def __init__(self, loras):
        super().__init__()
        self.loras = loras


def test_layers_are_marked_with_their_file_found_and_set_per_picture(tmp_path):
    a, b, c = (str(tmp_path / f"{n}.safetensors") for n in "abc")

    class Loader:
        @staticmethod
        def _apply_single_lora(transformer, lora_file, scale, mapping, *, role=None):
            # file a touches block 0 alone; b and c both touch block 1, which becomes a stack; c is a LoKr
            if lora_file.endswith("a.safetensors"):
                transformer["blocks"][0]["wq"] = LoRALinear(scale)
            elif lora_file.endswith("b.safetensors"):
                transformer["blocks"][1]["wq"] = FusedLoRALinear([LoRALinear(scale)])
            else:
                transformer["blocks"][1]["wq"].loras.append(LoKrLinear(scale))

    worker.tag_layers(Loader, (LoRALinear, LoKrLinear), [a, b, c])
    transformer = Module()
    transformer["blocks"] = [Module(), Module()]
    for path in (a, b, c):
        Loader._apply_single_lora(transformer, path, 1.0, None, role=None)
    layers, stacks = worker.find_layers(transformer, (LoRALinear, LoKrLinear), FusedLoRALinear)
    assert sorted(layer._formcut_file for layer in layers) == sorted([a, b, c]) and len(stacks) == 1
    # a picture using a at 0.8 and c at -1.5: b set aside from the stack, a and c at their scales
    active = worker.set_scales(layers, stacks, {a: 0.8, c: -1.5})
    by_file = {layer._formcut_file: layer for layer in layers}
    assert active == 2 and by_file[a].scale == 0.8 and by_file[c].scale == -1.5 and by_file[b].scale == 0.0
    assert [lora._formcut_file for lora in stacks[0].loras] == [c]
    # the next picture using b alone: the stack holds b again, a at 0
    worker.set_scales(layers, stacks, {b: 1.2})
    assert [lora._formcut_file for lora in stacks[0].loras] == [b] and by_file[a].scale == 0.0 and by_file[b].scale == 1.2
    # a picture with no LoRA: the stack empty, every layer at 0
    assert worker.set_scales(layers, stacks, {}) == 0 and stacks[0].loras == []


def test_the_worker_uses_only_names_mflux_has():
    """Every mflux name the worker imports or calls, written as mflux 0.20.0 spells it."""
    source = WORKER.read_text(encoding="utf-8")
    for name in (
        "from mflux.models.krea2.cli.krea2_generate import build_parser",
        "from mflux.cli.parser.parsers import lora_init_kwargs_from_args",
        "from mflux.callbacks.callback_manager import CallbackManager",
        "from mflux.models.common.resolution.config_resolution import ConfigResolution",
        "from mflux.models.krea2.variants.txt2img.krea2 import Krea2",
        "from mflux.models.common.lora.layer.fused_linear_lora_layer import FusedLoRALinear",
        "model.generate_image(",
        "num_inference_steps=",
        "image.save(path=",
    ):
        assert name in source, name
