"""LoRAs checked against mflux's own key mapping, renamed where that makes them apply (v2.2.9). The owner: several
OneTrainer and Civitai LoRAs did not work with mflux. A stand-in mflux here carries the Krea 2 mapping's shape (the
same pattern rules, prefixes and suffixes); with MFLUX_SRC pointing at a real mflux source the same checks run
against it."""

from __future__ import annotations

import json
import os
import struct
import sys
import textwrap
from pathlib import Path

import pytest
from app import lora_audit, loras

MAPPING = """
from dataclasses import dataclass, field
from typing import List
@dataclass
class LoRATarget:
    model_path: str
    possible_up_patterns: List[str]
    possible_down_patterns: List[str]
    possible_alpha_patterns: List[str] = field(default_factory=list)
    possible_lokr_w1_patterns: List[str] = field(default_factory=list)
    possible_lokr_w2_patterns: List[str] = field(default_factory=list)
    possible_dora_scale_patterns: List[str] = field(default_factory=list)
class LoRAMapping:
    pass
"""

KREA = """
from mflux.models.common.lora.mapping.lora_mapping import LoRAMapping, LoRATarget
class Krea2LoRAMapping(LoRAMapping):
    @staticmethod
    def get_mapping():
        out = []
        for mlx, diffusers in (("blocks.{block}.attn.wq", "transformer_blocks.{block}.attn.to_q"), ("first", "img_in")):
            paths = [mlx, diffusers]
            flat = [p.replace(".", "_") for p in paths]
            def patterns(ups):
                found = [f"{pre}{p}.{s}" for p in paths for pre in ("", "transformer.", "diffusion_model.", "base_model.model.") for s in ups]
                return found
            out.append(LoRATarget(
                model_path=mlx,
                possible_up_patterns=patterns(["lora_B.weight", "lora_up.weight"]) + [f"lora_unet_{f}.lora_up.weight" for f in flat],
                possible_down_patterns=patterns(["lora_A.weight", "lora_down.weight"]) + [f"lora_unet_{f}.lora_down.weight" for f in flat],
                possible_alpha_patterns=[f"{pre}{p}.alpha" for p in paths for pre in ("", "transformer.")] + [f"lora_unet_{f}.alpha" for f in flat],
                possible_lokr_w1_patterns=[f"{pre}{p}.lokr_w1" for p in paths for pre in ("", "transformer.")],
                possible_lokr_w2_patterns=[f"{pre}{p}.lokr_w2" for p in paths for pre in ("", "transformer.")],
            ))
        return out
"""


@pytest.fixture
def mflux(tmp_path, monkeypatch):
    real = os.environ.get("MFLUX_SRC")
    if real:
        monkeypatch.setenv("PYTHONPATH", real)
        return Path(real)
    root = tmp_path / "fake-mflux"
    for folder in (
        "mflux",
        "mflux/models",
        "mflux/models/common",
        "mflux/models/common/lora",
        "mflux/models/common/lora/mapping",
        "mflux/models/krea2",
        "mflux/models/krea2/weights",
    ):
        (root / folder).mkdir(parents=True, exist_ok=True)
        (root / folder / "__init__.py").write_text("")
    (root / "mflux/models/common/lora/mapping/lora_mapping.py").write_text(textwrap.dedent(MAPPING))
    (root / "mflux/models/krea2/weights/krea2_lora_mapping.py").write_text(textwrap.dedent(KREA))
    monkeypatch.setenv("PYTHONPATH", str(root))
    return root


def _lora(path: Path, keys: list[str]) -> Path:
    header, offset = {}, 0
    for key in keys:
        size = 2 if key.endswith("alpha") else 64
        header[key] = {"dtype": "F16", "shape": [] if key.endswith("alpha") else [4, 8], "data_offsets": [offset, offset + size]}
        offset += size
    text = json.dumps(header).encode()
    text += b" " * (-len(text) % 8)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<Q", len(text)) + text + bytes(i % 251 for i in range(offset)))
    return path


LAYOUTS = {
    "diffusers": ["transformer.transformer_blocks.0.attn.to_q.lora_A.weight", "transformer.transformer_blocks.0.attn.to_q.lora_B.weight"],
    "kohya": [
        "lora_unet_blocks_0_attn_wq.lora_down.weight",
        "lora_unet_blocks_0_attn_wq.lora_up.weight",
        "lora_unet_blocks_0_attn_wq.alpha",
    ],
    "onetrainer": [
        "lora_transformer_transformer_blocks_1_attn_to_q.lora_down.weight",
        "lora_transformer_transformer_blocks_1_attn_to_q.lora_up.weight",
        "lora_te1_encoder_layers_0_q_proj.lora_down.weight",
    ],
    "lycoris": ["lycoris_blocks_2_attn_wq.lokr_w1", "lycoris_blocks_2_attn_wq.lokr_w2"],
    "dora": [
        "lora_unet_blocks_0_attn_wq.lora_down.weight",
        "lora_unet_blocks_0_attn_wq.lora_up.weight",
        "lora_unet_blocks_0_attn_wq.dora_scale",
    ],
    "loha": ["lora_unet_blocks_0_attn_wq.hada_w1_a", "lora_unet_blocks_0_attn_wq.hada_w1_b"],
    "flux1": ["lora_unet_double_blocks_0_img_attn_qkv.lora_down.weight", "lora_unet_double_blocks_0_img_attn_qkv.lora_up.weight"],
}


def test_each_layout_is_read_renamed_or_named_for_what_it_is(tmp_path, mflux):
    jobs = [{"path": str(_lora(tmp_path / f"{name}.safetensors", keys)), "model": "krea-2"} for name, keys in LAYOUTS.items()]
    found = {Path(path).stem: result for path, result in lora_audit.run(Path(sys.executable), jobs).items()}
    said = {name: lora_audit.summary(result, "Krea 2") for name, result in found.items()}
    assert said["diffusers"] == (True, "all 2 keys apply") and said["kohya"] == (True, "all 3 keys apply")
    assert (
        found["onetrainer"]["renames"]["lora_transformer_transformer_blocks_1_attn_to_q.lora_down.weight"]
        == "lora_unet_transformer_blocks_1_attn_to_q.lora_down.weight"
    )
    assert said["onetrainer"][0] and "text-encoder" in said["onetrainer"][1]
    assert found["lycoris"]["renames"]["lycoris_blocks_2_attn_wq.lokr_w1"] == "blocks.2.attn.wq.lokr_w1"
    assert said["dora"][0] and "DoRA magnitude is not applied" in said["dora"][1]
    assert said["loha"] == (False, "it is a LoHa, which mflux does not load")
    assert not said["flux1"][0] and "made for another model" in said["flux1"][1]


def test_a_renamed_copy_keeps_every_tensor_byte(tmp_path):
    source = _lora(tmp_path / "in.safetensors", LAYOUTS["onetrainer"])
    copy = lora_audit.rewrite(source, tmp_path / "out" / "in.safetensors", {LAYOUTS["onetrainer"][0]: "renamed.lora_down.weight"})

    def parts(path):
        raw = path.read_bytes()
        (length,) = struct.unpack("<Q", raw[:8])
        return json.loads(raw[8 : 8 + length]), raw[8 + length :]

    (before, data_before), (after, data_after) = parts(source), parts(copy)
    assert data_before == data_after and "renamed.lora_down.weight" in after and LAYOUTS["onetrainer"][0] not in after
    assert after["renamed.lora_down.weight"] == before[LAYOUTS["onetrainer"][0]]


def test_the_library_gives_mflux_the_renamed_copy_and_refuses_what_cannot_apply(tmp_path, mflux, monkeypatch):
    monkeypatch.setattr(loras, "LIBRARY", tmp_path / "loras")
    monkeypatch.setattr(loras, "_runtime_python", lambda: Path(sys.executable))
    monkeypatch.setattr(loras, "_MFLUX", {})
    folder = tmp_path / "loras" / "krea-2"
    _lora(folder / "OneTrainer Style.safetensors", LAYOUTS["onetrainer"])
    _lora(folder / "Old Flux.safetensors", LAYOUTS["flux1"])
    listed = {entry["name"]: entry for entry in loras.entries("krea-2")}
    style, old = listed["OneTrainer Style"], listed["Old Flux"]
    assert style["usable"] and style["audit"]["converted"] == "OneTrainer Style.safetensors"
    assert not old["usable"] and "made for another model" in old["problem"]
    [(path, scale)] = loras.resolve([{"id": style["id"], "scale": 0.8}], "krea-2")
    assert Path(path).parts[-2:] == (".converted", "OneTrainer Style.safetensors") and scale == 0.8
    with pytest.raises(ValueError, match="cannot be used"):
        loras.resolve([{"id": old["id"], "scale": 1}], "krea-2")
    # checked once: the record remembers it while the file and mflux are unchanged
    assert json.loads((folder / "OneTrainer Style.json").read_text())["audit"]["applies"] is True
