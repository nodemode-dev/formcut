import hashlib
import json
import os
import shutil
import threading
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import jobs
from .paths import DATA_DIR, MODELS_DIR

router = APIRouter(prefix="/api/models", tags=["models"])
ROOT = MODELS_DIR
LEGACY = DATA_DIR / "models"
# BG2: models shipped inside the engine build, so the default cutout works on
# a machine that has downloaded nothing. A file in the person's model folder
# always takes precedence; the bundle only answers when the folder is empty.
# Resolved the way effect_packages resolves its library: beside this module,
# which under PyInstaller lands at _MEIPASS/app/bundled_models via freeze.py.
BUNDLED = Path(__file__).resolve().parent / "bundled_models"


def model_file(name: str) -> Path:
    """Where a model file actually is: the model folder, else the bundle."""
    path = ROOT / name
    if path.is_file() and path.stat().st_size > (1024 if path.suffix in (".onnx", ".bin", ".pth", ".safetensors") else 0):
        return path
    bundled = BUNDLED / name
    if bundled.is_file():
        return bundled
    return path


# BG6: one ordering for every ONNX Runtime session the engine opens. The
# platform accelerator comes first where its provider is present (Core ML on
# macOS in the standard wheel, DirectML on Windows via onnxruntime-directml,
# CUDA on Linux via onnxruntime-gpu), and the CPU provider is always the
# floor, so a machine with nothing extra runs everything unchanged.
PROVIDERS = ("CoreMLExecutionProvider", "DmlExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider")


def providers() -> list[str]:
    """The execution providers to hand a session, best first."""
    import onnxruntime as ort

    available = ort.get_available_providers()
    return [name for name in PROVIDERS if name in available] or ["CPUExecutionProvider"]


MODELS = {
    # Krea 2 Turbo, optional and never fetched on its own: krea2.py records the licence accepted before these downloads
    # may start, and installs the content filter (the classifier section 4.2 of that licence names) with every build.
    # Every file pinned below to its SHA-256.
    "krea-2-mlx-q8": {
        "name": "Krea 2 Turbo, 8-bit MLX (mflux-community)",
        "license": "Krea 2 Community License Agreement",
        "optional": True,
        "consent": "krea-2",
        "maxFileBytes": 2241144740,
        # mflux-community/krea-2-turbo-mflux-q8 at 5f94d7734c8873daddf803721f6423148619f63c, 19 files, 22.19 GB
        "files": {
            "krea-2-mlx-q8/.DS_Store": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/.DS_Store",
            "krea-2-mlx-q8/0.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/0.safetensors",
            "krea-2-mlx-q8/1.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/1.safetensors",
            "krea-2-mlx-q8/2.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/2.safetensors",
            "krea-2-mlx-q8/3.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/3.safetensors",
            "krea-2-mlx-q8/4.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/4.safetensors",
            "krea-2-mlx-q8/5.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/5.safetensors",
            "krea-2-mlx-q8/6.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/6.safetensors",
            "krea-2-mlx-q8/model.safetensors.index.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/model.safetensors.index.json",
            "krea-2-mlx-q8/text_encoder/0.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/text_encoder/0.safetensors",
            "krea-2-mlx-q8/text_encoder/1.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/text_encoder/1.safetensors",
            "krea-2-mlx-q8/text_encoder/2.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/text_encoder/2.safetensors",
            "krea-2-mlx-q8/text_encoder/3.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/text_encoder/3.safetensors",
            "krea-2-mlx-q8/text_encoder/model.safetensors.index.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/text_encoder/model.safetensors.index.json",
            "krea-2-mlx-q8/tokenizer/chat_template.jinja": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/tokenizer/chat_template.jinja",
            "krea-2-mlx-q8/tokenizer/tokenizer.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/tokenizer/tokenizer.json",
            "krea-2-mlx-q8/tokenizer/tokenizer_config.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/tokenizer/tokenizer_config.json",
            "krea-2-mlx-q8/vae/0.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/vae/0.safetensors",
            "krea-2-mlx-q8/vae/model.safetensors.index.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q8/resolve/5f94d7734c8873daddf803721f6423148619f63c/vae/model.safetensors.index.json",
        },
    },
    "krea-2-mlx-q4": {
        "name": "Krea 2 Turbo, 4-bit MLX (mflux-community)",
        "license": "Krea 2 Community License Agreement",
        "optional": True,
        "consent": "krea-2",
        "maxFileBytes": 2242209936,
        # mflux-community/krea-2-turbo-mflux-q4 at fa0ba74dc2e50c4288a81216e05487c343196bf7, 16 files, 15.78 GB
        "files": {
            "krea-2-mlx-q4/.DS_Store": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/.DS_Store",
            "krea-2-mlx-q4/0.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/0.safetensors",
            "krea-2-mlx-q4/1.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/1.safetensors",
            "krea-2-mlx-q4/2.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/2.safetensors",
            "krea-2-mlx-q4/3.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/3.safetensors",
            "krea-2-mlx-q4/model.safetensors.index.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/model.safetensors.index.json",
            "krea-2-mlx-q4/text_encoder/0.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/text_encoder/0.safetensors",
            "krea-2-mlx-q4/text_encoder/1.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/text_encoder/1.safetensors",
            "krea-2-mlx-q4/text_encoder/2.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/text_encoder/2.safetensors",
            "krea-2-mlx-q4/text_encoder/3.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/text_encoder/3.safetensors",
            "krea-2-mlx-q4/text_encoder/model.safetensors.index.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/text_encoder/model.safetensors.index.json",
            "krea-2-mlx-q4/tokenizer/chat_template.jinja": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/tokenizer/chat_template.jinja",
            "krea-2-mlx-q4/tokenizer/tokenizer.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/tokenizer/tokenizer.json",
            "krea-2-mlx-q4/tokenizer/tokenizer_config.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/tokenizer/tokenizer_config.json",
            "krea-2-mlx-q4/vae/0.safetensors": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/vae/0.safetensors",
            "krea-2-mlx-q4/vae/model.safetensors.index.json": "https://huggingface.co/mflux-community/krea-2-turbo-mflux-q4/resolve/fa0ba74dc2e50c4288a81216e05487c343196bf7/vae/model.safetensors.index.json",
        },
    },
    "krea-2-sdnq-int8": {
        "name": "Krea 2 Turbo, 8-bit SDNQ (diffusers)",
        "license": "Krea 2 Community License Agreement",
        "optional": True,
        "consent": "krea-2",
        "maxFileBytes": 10088722566,
        # OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit at dfa31958258de845f21a86e0dd0566f46d3a7970, 14 files, 18.30 GB
        "files": {
            "krea-2-sdnq-int8/LICENSE.pdf": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/LICENSE.pdf",
            "krea-2-sdnq-int8/model_index.json": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/model_index.json",
            "krea-2-sdnq-int8/scheduler/scheduler_config.json": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/scheduler/scheduler_config.json",
            "krea-2-sdnq-int8/text_encoder/config.json": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/text_encoder/config.json",
            "krea-2-sdnq-int8/text_encoder/model.safetensors": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/text_encoder/model.safetensors",
            "krea-2-sdnq-int8/tokenizer/chat_template.jinja": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/tokenizer/chat_template.jinja",
            "krea-2-sdnq-int8/tokenizer/tokenizer.json": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/tokenizer/tokenizer.json",
            "krea-2-sdnq-int8/tokenizer/tokenizer_config.json": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/tokenizer/tokenizer_config.json",
            "krea-2-sdnq-int8/transformer/config.json": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/transformer/config.json",
            "krea-2-sdnq-int8/transformer/diffusion_pytorch_model-00001-of-00002.safetensors": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/transformer/diffusion_pytorch_model-00001-of-00002.safetensors",
            "krea-2-sdnq-int8/transformer/diffusion_pytorch_model-00002-of-00002.safetensors": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/transformer/diffusion_pytorch_model-00002-of-00002.safetensors",
            "krea-2-sdnq-int8/transformer/diffusion_pytorch_model.safetensors.index.json": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/transformer/diffusion_pytorch_model.safetensors.index.json",
            "krea-2-sdnq-int8/vae/config.json": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/vae/config.json",
            "krea-2-sdnq-int8/vae/diffusion_pytorch_model.safetensors": "https://huggingface.co/OzzyGT/Krea_2_Turbo_sdnq_dynamic_8bit/resolve/dfa31958258de845f21a86e0dd0566f46d3a7970/vae/diffusion_pytorch_model.safetensors",
        },
    },
    # FLUX.2 [klein] 4B (Apache-2.0), optional, installed from its card (klein.py); every file pinned below to its
    # SHA-256. The 9B models (FLUX Non-Commercial License) are not offered.
    "flux2-klein-4b-mlx-q8": {
        "name": "FLUX.2 [klein] 4B, 8-bit MLX (mflux-community)",
        "license": "Apache-2.0",
        "optional": True,
        "consent": "klein-4b",
        "maxFileBytes": 2145931486,
        # mflux-community/flux2-klein-4b-mflux-q8 at ca49409e4ce21c6717ee87caadd9488e0b15208f, 11 files, 8.57 GB
        "files": {
            "flux2-klein-4b-mlx-q8/text_encoder/0.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/text_encoder/0.safetensors",
            "flux2-klein-4b-mlx-q8/text_encoder/1.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/text_encoder/1.safetensors",
            "flux2-klein-4b-mlx-q8/text_encoder/model.safetensors.index.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/text_encoder/model.safetensors.index.json",
            "flux2-klein-4b-mlx-q8/tokenizer/chat_template.jinja": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/tokenizer/chat_template.jinja",
            "flux2-klein-4b-mlx-q8/tokenizer/tokenizer.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/tokenizer/tokenizer.json",
            "flux2-klein-4b-mlx-q8/tokenizer/tokenizer_config.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/tokenizer/tokenizer_config.json",
            "flux2-klein-4b-mlx-q8/transformer/0.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/transformer/0.safetensors",
            "flux2-klein-4b-mlx-q8/transformer/1.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/transformer/1.safetensors",
            "flux2-klein-4b-mlx-q8/transformer/model.safetensors.index.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/transformer/model.safetensors.index.json",
            "flux2-klein-4b-mlx-q8/vae/0.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/vae/0.safetensors",
            "flux2-klein-4b-mlx-q8/vae/model.safetensors.index.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q8/resolve/ca49409e4ce21c6717ee87caadd9488e0b15208f/vae/model.safetensors.index.json",
        },
    },
    "flux2-klein-4b-mlx-q4": {
        "name": "FLUX.2 [klein] 4B, 4-bit MLX (mflux-community)",
        "license": "Apache-2.0",
        "optional": True,
        "consent": "klein-4b",
        "maxFileBytes": 2145323770,
        # mflux-community/flux2-klein-4b-mflux-q4 at 794cd159538149ad9830848508c31f0ea7088e58, 11 files, 4.62 GB
        "files": {
            "flux2-klein-4b-mlx-q4/text_encoder/0.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/text_encoder/0.safetensors",
            "flux2-klein-4b-mlx-q4/text_encoder/1.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/text_encoder/1.safetensors",
            "flux2-klein-4b-mlx-q4/text_encoder/model.safetensors.index.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/text_encoder/model.safetensors.index.json",
            "flux2-klein-4b-mlx-q4/tokenizer/chat_template.jinja": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/tokenizer/chat_template.jinja",
            "flux2-klein-4b-mlx-q4/tokenizer/tokenizer.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/tokenizer/tokenizer.json",
            "flux2-klein-4b-mlx-q4/tokenizer/tokenizer_config.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/tokenizer/tokenizer_config.json",
            "flux2-klein-4b-mlx-q4/transformer/0.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/transformer/0.safetensors",
            "flux2-klein-4b-mlx-q4/transformer/1.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/transformer/1.safetensors",
            "flux2-klein-4b-mlx-q4/transformer/model.safetensors.index.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/transformer/model.safetensors.index.json",
            "flux2-klein-4b-mlx-q4/vae/0.safetensors": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/vae/0.safetensors",
            "flux2-klein-4b-mlx-q4/vae/model.safetensors.index.json": "https://huggingface.co/mflux-community/flux2-klein-4b-mflux-q4/resolve/794cd159538149ad9830848508c31f0ea7088e58/vae/model.safetensors.index.json",
        },
    },
    "nsfw-filter": {
        "name": "Falconsai/nsfw_image_detection (ONNX), the content filter for Krea 2",
        "license": "Apache-2.0",
        "optional": True,
        "maxFileBytes": 2000000000,
        # onnx-community/nsfw_image_detection-ONNX at 1ceb3c7fe1e9f3f2507e6df577437f23a9149fd5, 4 files, 0.34 GB
        "files": {
            "nsfw-filter/config.json": "https://huggingface.co/onnx-community/nsfw_image_detection-ONNX/resolve/1ceb3c7fe1e9f3f2507e6df577437f23a9149fd5/config.json",
            "nsfw-filter/onnx/model.onnx": "https://huggingface.co/onnx-community/nsfw_image_detection-ONNX/resolve/1ceb3c7fe1e9f3f2507e6df577437f23a9149fd5/onnx/model.onnx",
            "nsfw-filter/preprocessor_config.json": "https://huggingface.co/onnx-community/nsfw_image_detection-ONNX/resolve/1ceb3c7fe1e9f3f2507e6df577437f23a9149fd5/preprocessor_config.json",
            "nsfw-filter/quantize_config.json": "https://huggingface.co/onnx-community/nsfw_image_detection-ONNX/resolve/1ceb3c7fe1e9f3f2507e6df577437f23a9149fd5/quantize_config.json",
        },
    },
    # Heavier segmentation, offered rather than required: the cutout works
    # without them and is better with them.
    "video-matting": {
        "name": "Robust Video Matting",
        "license": "GPL-3.0-only",
        "note": "not bundled; fetched only if a person asks for it",
        "files": {
            "rvm_mobilenetv3_fp32.onnx": "https://github.com/PeterL1n/RobustVideoMatting/releases/download/v1.0.0/rvm_mobilenetv3_fp32.onnx"
        },
    },
    "sharp-cutout": {
        "name": "IS-Net general matting",
        "license": "Apache-2.0",
        "files": {"isnet-general-use.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"},
    },
    "click-select": {
        "name": "SAM 2 Hiera Tiny",
        "license": "Apache-2.0",
        # SAM 2 ships as PyTorch weights; these are the ONNX exports an engine
        # running ONNX Runtime can load. The url here first was a file that does
        # not exist, which is why it returned 404 rather than downloading.
        "files": {
            "sam2_hiera_tiny.encoder.onnx": "https://huggingface.co/vietanhdev/segment-anything-2-onnx-models/resolve/main/sam2_hiera_tiny.encoder.onnx",
            "sam2_hiera_tiny.decoder.onnx": "https://huggingface.co/vietanhdev/segment-anything-2-onnx-models/resolve/main/sam2_hiera_tiny.decoder.onnx",
        },
    },
    "click-track": {
        "name": "SAM 2.1 video tracking",
        "license": "Apache-2.0",
        # SAM 2.1 Hiera Tiny with its memory encoder, memory attention and
        # object pointers, so a point on one frame is followed through a clip.
        "files": {
            f"sam21-video-{name}": f"https://huggingface.co/square-zero-labs/sam2.1-tiny-video-onnx/resolve/main/{path}"
            for name, path in (
                ("vision_encoder.onnx", "onnx/vision_encoder.onnx"),
                ("mask_decoder.onnx", "onnx/mask_decoder.onnx"),
                ("memory_encoder.onnx", "onnx/memory_encoder.onnx"),
                ("memory_attention.onnx", "onnx/memory_attention.onnx"),
                ("pointer_tpos.onnx", "onnx/pointer_tpos.onnx"),
                ("constants.json", "constants.json"),
            )
        },
    },
    "object-cutout": {
        "name": "Object cutout (U2Net small)",
        "license": "Apache-2.0",
        "files": {"u2netp.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"},
    },
    "person-cutout": {
        "name": "Person cutout (U2Net)",
        "license": "Apache-2.0",
        "files": {"u2net_human_seg.onnx": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx"},
    },
    "local-image": {
        # A model the local generator can run out of the box, downloaded on
        # request and never on boot: SD Turbo's ONNX export, 2.4 GB, one step
        # a picture. Its licence is Stability's non-commercial research
        # licence and the panel shows it before the download starts; a person
        # who needs commercial terms declares another model in the slot
        # registry instead. The files land in the diffusers layout the local
        # diffusion runner reads (models/diffusion/sd-turbo).
        "name": "SD Turbo (local image generation)",
        "license": "Stability AI Non-Commercial Research Community License (non-commercial)",
        "optional": True,
        # onnxruntime/sd-turbo at 80d4d2e238a7c61a83053b931f2354ab43dd3688, 10 files; that revision has no unet or
        # vae_decoder config.json, which the runner treats as optional
        "files": {
            "diffusion/sd-turbo/LICENSE": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/LICENSE",
            "diffusion/sd-turbo/model_index.json": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/model_index.json",
            "diffusion/sd-turbo/scheduler/scheduler_config.json": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/scheduler/scheduler_config.json",
            "diffusion/sd-turbo/tokenizer/merges.txt": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/tokenizer/merges.txt",
            "diffusion/sd-turbo/tokenizer/special_tokens_map.json": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/tokenizer/special_tokens_map.json",
            "diffusion/sd-turbo/tokenizer/tokenizer_config.json": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/tokenizer/tokenizer_config.json",
            "diffusion/sd-turbo/tokenizer/vocab.json": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/tokenizer/vocab.json",
            "diffusion/sd-turbo/text_encoder/model.onnx": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/text_encoder/model.onnx",
            "diffusion/sd-turbo/unet/model.onnx": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/unet/model.onnx",
            "diffusion/sd-turbo/vae_decoder/model.onnx": "https://huggingface.co/onnxruntime/sd-turbo/resolve/80d4d2e238a7c61a83053b931f2354ab43dd3688/vae_decoder/model.onnx",
        },
    },
    "ai-upscale": {
        "name": "Real-ESRGAN x4plus",
        "license": "BSD-3-Clause",
        # Converted to ONNX from the official RealESRGAN_x4plus.pth by a published,
        # reproducible recipe; pinned below to the converter's stated SHA-256.
        "files": {"realesrgan-x4plus.onnx": "https://huggingface.co/skillsafe-ai/realesrgan-x4plus/resolve/main/model.onnx"},
    },
    "local-speech": {
        "name": "Kokoro local speech",
        "license": "Apache-2.0",
        "files": {
            "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx",
            "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin",
        },
    },
    "voice-activity": {
        "name": "Silero VAD",
        "license": "MIT",
        # whether someone is speaking, under music too: the cut check refuses an edit with speech on both sides
        "files": {
            "silero_vad.onnx": "https://github.com/snakers4/silero-vad/raw/5cd7945676eb32225748052e2e6a0580e4686a08/src/silero_vad/data/silero_vad.onnx",
        },
    },
}
_lock = threading.RLock()
_downloading: set[str] = set()


def ready(model: str) -> bool:
    """Every file of the model is there: weights past the one-kilobyte floor, a config or licence file merely non-empty."""
    if model not in MODELS:
        return False
    for name in MODELS[model]["files"]:
        path = model_file(name)
        if not path.is_file():
            return False
        floor = 1024 if path.suffix in (".onnx", ".bin", ".pth", ".safetensors") else 1
        if path.stat().st_size < floor:
            return False
    return True


@router.get("/runtime")
def runtime():
    """BG6: what this machine offers and which provider sessions will use."""
    import onnxruntime as ort

    chosen = providers()
    return {"active": chosen[0], "available": ort.get_available_providers()}


@router.get("")
def list_models():
    return [
        {
            "id": key,
            "name": spec["name"],
            "license": spec["license"],
            "ready": ready(key),
            "downloading": key in _downloading,
            "files": list(spec["files"]),
            # Krea 2's builds and its filter are installed from their own card, after the licence and the filter choice
            "managedBy": "krea-2"
            if spec.get("consent") == "krea-2" or key == "nsfw-filter"
            else ("klein" if str(spec.get("consent", "")).startswith("klein") else None),
        }
        for key, spec in MODELS.items()
    ]


def download(model: str, report, cancelled):
    if model not in MODELS:
        raise ValueError("Unknown model")
    ROOT.mkdir(parents=True, exist_ok=True)
    with _lock:
        entries = list(MODELS[model]["files"].items())
        for i, (name, url) in enumerate(entries):
            path = ROOT / name
            if path.is_file():
                continue
            # A per-model source may override the declared one; keeping it in a
            # separate name makes clear the loop's value is not being rewritten.
            download_url = source_for(model, name, url)
            if not PINNED.get(name) and not MODELS[model].get("added"):
                raise ValueError(f"{name} has no pinned checksum, so it is not downloaded")
            limit = int(MODELS[model].get("maxFileBytes", 2_000_000_000))
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".download")
            digest = hashlib.sha256()
            try:
                with httpx.stream("GET", download_url, follow_redirects=True, timeout=120) as response:
                    response.raise_for_status()
                    length = int(response.headers.get("content-length", 0))
                    written = 0
                    with temporary.open("wb") as out:
                        for chunk in response.iter_bytes(1024 * 1024):
                            if cancelled():
                                raise InterruptedError("Cancelled")
                            written += len(chunk)
                            if written > limit:
                                raise ValueError("Model exceeds the download limit")
                            out.write(chunk)
                            digest.update(chunk)
                            report((i + (written / length if length else 0.5)) / len(entries))
                # the one-kilobyte floor is for weights; a model's config or tokenizer file can be smaller
                if temporary.stat().st_size < (1024 if path.suffix in (".onnx", ".bin", ".pth", ".safetensors", ".gguf") else 1):
                    raise ValueError("Model download is incomplete")
                expected = PINNED.get(name)
                if expected and digest.hexdigest() != expected:
                    # P8: a file that does not match its pin never lands. It is
                    # deleted and named, so a bad mirror cannot poison the cache.
                    temporary.unlink(missing_ok=True)
                    raise ValueError(f"Checksum mismatch for {name}: expected {expected[:16]}..., got {digest.hexdigest()[:16]}...")
                temporary.replace(path)
                path.with_suffix(path.suffix + ".json").write_text(
                    json.dumps({"url": download_url, "sha256": digest.hexdigest(), "license": MODELS[model]["license"]})
                )
            finally:
                temporary.unlink(missing_ok=True)
    return {"model": model, "ready": ready(model)}


def _tracked(model: str, report, cancelled):
    _downloading.add(model)
    try:
        return download(model, report, cancelled)
    finally:
        _downloading.discard(model)


@router.post("/{model}/download", status_code=202)
def start_download(model: str):
    if model not in MODELS:
        raise HTTPException(404, "Unknown model")
    if MODELS[model].get("consent") == "krea-2":
        from .krea2 import consent

        if not consent().get("licence"):
            raise HTTPException(409, "Krea 2 is installed from its own panel, once its licence is accepted")
    if str(MODELS[model].get("consent", "")).startswith("klein"):
        from .klein import consent as klein_consent

        variant = "flux2-" + MODELS[model]["consent"]
        if not klein_consent().get(variant, {}).get("licence"):
            raise HTTPException(409, "FLUX.2 [klein] is installed from its own card, once its licence is accepted")
    return jobs.submit("model-download", lambda _id, report, cancelled: _tracked(model, report, cancelled))


def adopt_legacy() -> list[str]:
    moved: list[str] = []
    if not LEGACY.is_dir() or LEGACY.resolve() == ROOT.resolve():
        return moved
    ROOT.mkdir(parents=True, exist_ok=True)
    for spec in MODELS.values():
        for name in spec["files"]:
            for candidate in (name, name + ".json"):
                source, target = LEGACY / candidate, ROOT / candidate
                if source.is_file() and not target.exists():
                    shutil.move(str(source), str(target))
                    moved.append(candidate)
    return moved


# What first launch fetches: the Creator panel's default cutout, a few megabytes.
# Everything else downloads when it is first used, from the button beside it,
# or for Whisper through the hub route the moment the transcriber asks.
FIRST_LAUNCH = ("object-cutout",)


def prepare(report, cancelled, fetch: bool, everything: bool = False) -> dict:
    """Fetch the first-launch models; with everything, every permissively licensed model and the Whisper files."""
    adopted = adopt_legacy()
    wanted = (
        [model for model in MODELS if "GPL" not in MODELS[model]["license"] and not MODELS[model].get("optional")]
        if everything
        else list(FIRST_LAUNCH)
    )
    missing = [model for model in wanted if not ready(model)] if fetch else []
    results = []
    for i, model in enumerate(missing):
        if cancelled():
            raise InterruptedError("Cancelled")
        try:
            results.append(_tracked(model, lambda fraction, i=i: report((i + fraction) / len(missing)), cancelled))
        except InterruptedError:
            raise
        except Exception as error:
            results.append({"model": model, "ready": False, "error": str(error)})
    hub = []
    for model, paths in HUB_PREFETCH.items() if fetch and everything else ():
        for path in paths:
            if cancelled():
                raise InterruptedError("Cancelled")
            try:
                hub.append({"file": f"{model}/{path}", "ready": hub_fetch(model, path) is not None})
            except Exception as error:
                hub.append({"file": f"{model}/{path}", "ready": False, "error": str(error)})
    return {"adopted": adopted, "downloads": results, "hub": hub}


def auto_download() -> dict:
    mode = os.environ.get("FORMCUT_MODELS_AUTO", "1")
    return jobs.submit("model-setup", lambda _id, report, cancelled: prepare(report, cancelled, mode != "0", mode == "all"))


HUB = ROOT / "hub"
# C1 offers tiny, base and small in English-only and multilingual form, so every
# one of those must be allowed through the hub or the worker's request is refused.
WHISPER_MODELS = (
    "Xenova/whisper-tiny.en",
    "Xenova/whisper-base.en",
    "Xenova/whisper-small.en",
    "onnx-community/whisper-tiny",
    "onnx-community/whisper-base",
    "onnx-community/whisper-small",
)
HUB_MODELS = set(WHISPER_MODELS)
# The engine's own transcriber (transcribe.py) also runs medium and large,
# which no webview holds; allowed through the hub, never prefetched (1.8 GB).
ENGINE_WHISPER_MODELS = ("Xenova/whisper-medium.en", "Xenova/whisper-medium", "onnx-community/whisper-large-v3-turbo")
HUB_MODELS.update(ENGINE_WHISPER_MODELS)
HUB_PREFETCH = {
    model: (
        "config.json",
        "generation_config.json",
        "preprocessor_config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "onnx/encoder_model_quantized.onnx",
        "onnx/decoder_model_merged_quantized.onnx",
    )
    for model in WHISPER_MODELS
}
_hub_lock = threading.Lock()
# Each Whisper repository is fetched at one revision, and only the files the window's and the engine's transcribers
# read, each pinned to its SHA-256 (Hugging Face's LFS hash for the ONNX files, the fetched file's hash for the rest,
# 23 October 2026). A path not listed is answered as missing.
HUB_REVISIONS = {
    "Xenova/whisper-tiny.en": "79fb389fc764e7c395bd330e9531d9d32ada7049",
    "Xenova/whisper-base.en": "95bf40a508535962c6483ead40270b2e32267508",
    "Xenova/whisper-small.en": "fa16a75f5d91e83ecb6a2ccb690f14d91ef00ca4",
    "onnx-community/whisper-tiny": "ff4177021cc41f7db950912b73ea4fdf7d01d8e7",
    "onnx-community/whisper-base": "1846881b6b3a3024392c1eea3ad983695bc23925",
    "onnx-community/whisper-small": "36050c46d777d46dc4b5f43f6d90574fc38f8732",
    "Xenova/whisper-medium.en": "4fbcf6e6deb6b1af698e6925bfe00730bd4be715",
    "Xenova/whisper-medium": "8c5b90880ab9f79487ab33613413431bf661d595",
    "onnx-community/whisper-large-v3-turbo": "360ebcde2559d60bb474678be3c1de9ef347d01a",
}
HUB_PINNED = {
    "Xenova/whisper-tiny.en/config.json": "37a1073be00d19118c06557896c7c148598f4d8277edc0f5bc07c9f5554839f1",
    "Xenova/whisper-tiny.en/generation_config.json": "132c95ba9db45f4498f2eab3fea7c1d6a174005010f8f6b7d20cfd5e9795996b",
    "Xenova/whisper-tiny.en/preprocessor_config.json": "a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d",
    "Xenova/whisper-tiny.en/tokenizer.json": "c6ee8f089220a5b1188f6426456772572671c6141ae007eecb83c6a8349f5deb",
    "Xenova/whisper-tiny.en/tokenizer_config.json": "e082c1ad251541bf277967a703252cddd4bb37a71a43737e03d050c22ec08238",
    "Xenova/whisper-tiny.en/onnx/encoder_model_quantized.onnx": "8cc3c6f8563d1b3fbd2c5af9f64c2bed8b020bc593c402d1ef53b9f08fbf1b90",
    "Xenova/whisper-tiny.en/onnx/decoder_model_merged_quantized.onnx": "dbb2e063b7fbc41d9803b9698f93ecb035c50cbb3fb87b56cb131e4a5eb99059",
    "Xenova/whisper-base.en/config.json": "5c390f2c6ba84ddeb7e362cd8b2123832911407850174e64d7081ccc36df2d64",
    "Xenova/whisper-base.en/generation_config.json": "1e57ed56ad1bd7f08a49ece7fe7daada674573805a35f8bdbbe68380aab5b1ee",
    "Xenova/whisper-base.en/preprocessor_config.json": "a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d",
    "Xenova/whisper-base.en/tokenizer.json": "c6ee8f089220a5b1188f6426456772572671c6141ae007eecb83c6a8349f5deb",
    "Xenova/whisper-base.en/tokenizer_config.json": "e082c1ad251541bf277967a703252cddd4bb37a71a43737e03d050c22ec08238",
    "Xenova/whisper-base.en/onnx/encoder_model_quantized.onnx": "d0d4e59e2842617b39787cece73d7e8f76f99b1697d3386c0e682eca2269f4a1",
    "Xenova/whisper-base.en/onnx/decoder_model_merged_quantized.onnx": "a25afc5858a20aabb7652cb2d555996ebe10691a69bbdb423d5073d52f060325",
    "Xenova/whisper-small.en/config.json": "afddc76e1d6b2e13e5a85a385d55d272ed61f6797d7d32895492620387336cf6",
    "Xenova/whisper-small.en/generation_config.json": "dde54f4ed982cf4f57450f2d23eb5f97dd64dbc390c66a635a34a57e965b16a7",
    "Xenova/whisper-small.en/preprocessor_config.json": "a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d",
    "Xenova/whisper-small.en/tokenizer.json": "c6ee8f089220a5b1188f6426456772572671c6141ae007eecb83c6a8349f5deb",
    "Xenova/whisper-small.en/tokenizer_config.json": "e082c1ad251541bf277967a703252cddd4bb37a71a43737e03d050c22ec08238",
    "Xenova/whisper-small.en/onnx/encoder_model_quantized.onnx": "dd37efa07dad7619592ef849a40317dcfd182a2e632275a53a023f02f685cfa7",
    "Xenova/whisper-small.en/onnx/decoder_model_merged_quantized.onnx": "7cff5df61a1809654a5e62d89cbb99e8231b229f41412ab626a1d8fff77397ab",
    "onnx-community/whisper-tiny/config.json": "46aeea0a406afbeb563fc8e59ca10609203df4299af6a83f73752fef369efd2d",
    "onnx-community/whisper-tiny/generation_config.json": "f5c67e5a4f7102f8cb4d058bc95da276bbc19eeec997267c3bb0f25ef68facd1",
    "onnx-community/whisper-tiny/preprocessor_config.json": "a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d",
    "onnx-community/whisper-tiny/tokenizer.json": "27fc476bfe7f17299480be2273fc0608e4d5a99aba2ab5dec5374b4482d1a566",
    "onnx-community/whisper-tiny/tokenizer_config.json": "2a4c4281cf9f51ac6ccc406fdc711a087afe6530f671fa7b80953edc498275ce",
    "onnx-community/whisper-tiny/onnx/encoder_model_quantized.onnx": "2af4a414ca47aa30f61246017e5fe82b0a8d229281d1255ba666a2a7f6b84d19",
    "onnx-community/whisper-tiny/onnx/decoder_model_merged_quantized.onnx": "25e807a962b6349356d0ea5d0dfe530b7e5bf0e2a484aeca0359d03143faddd3",
    "onnx-community/whisper-base/config.json": "f4d0608f7d918166da7edb3e188de5ef1bfe70d9802e785d271fd88111e9cf4b",
    "onnx-community/whisper-base/generation_config.json": "61070cf8de25b1e9256e8e102ded49d8d24a8369ed36ef84fdf21549e68125a0",
    "onnx-community/whisper-base/preprocessor_config.json": "a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d",
    "onnx-community/whisper-base/tokenizer.json": "27fc476bfe7f17299480be2273fc0608e4d5a99aba2ab5dec5374b4482d1a566",
    "onnx-community/whisper-base/tokenizer_config.json": "2e036e4dbacfdeb7242c7d4ec4149f4a16e86026048f94d1637e3a8ee9c6a573",
    "onnx-community/whisper-base/onnx/encoder_model_quantized.onnx": "5862993336bf33acd23736071aae2b32261d3b1b2f37780194460d4ef974dd46",
    "onnx-community/whisper-base/onnx/decoder_model_merged_quantized.onnx": "fa3ef9902734ce5ae6f9ef2bdb2ba9a6c4b5785b09f4f420ce036573dc9d090b",
    "onnx-community/whisper-small/config.json": "457854d452f17661e197d74aee12b8e74fb75ba30ebfaa7426d0d61ea1e08a18",
    "onnx-community/whisper-small/generation_config.json": "f538b28220c6a6d6f1af1458d4141cacb4ef4963df3de98a19490440c412ddf0",
    "onnx-community/whisper-small/preprocessor_config.json": "a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d",
    "onnx-community/whisper-small/tokenizer.json": "27fc476bfe7f17299480be2273fc0608e4d5a99aba2ab5dec5374b4482d1a566",
    "onnx-community/whisper-small/tokenizer_config.json": "2a4c4281cf9f51ac6ccc406fdc711a087afe6530f671fa7b80953edc498275ce",
    "onnx-community/whisper-small/onnx/encoder_model_quantized.onnx": "a43a83f3c5361cd591cfa7c36f14b43cf7cb22f47a415cc14a8d557be800fa92",
    "onnx-community/whisper-small/onnx/decoder_model_merged_quantized.onnx": "ec07c3cbb64172c39791e26ee870a65ac22b458c36722bfe2776b3dbf741e0c9",
    "Xenova/whisper-medium.en/config.json": "dcf21f63715cddd621a286a9fa7f49a273e5aeb49dc3fd255ba96f7c0df2367b",
    "Xenova/whisper-medium.en/generation_config.json": "c018584392aba8786e9c944475fa17656b65801809ff1082d644989d90b17eec",
    "Xenova/whisper-medium.en/preprocessor_config.json": "a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d",
    "Xenova/whisper-medium.en/tokenizer.json": "c6ee8f089220a5b1188f6426456772572671c6141ae007eecb83c6a8349f5deb",
    "Xenova/whisper-medium.en/tokenizer_config.json": "e082c1ad251541bf277967a703252cddd4bb37a71a43737e03d050c22ec08238",
    "Xenova/whisper-medium.en/onnx/encoder_model_quantized.onnx": "c6fdaff8017b837b7b205ccd1d5f283008f4ee9677a29e503b3cf8e68efa9bb3",
    "Xenova/whisper-medium.en/onnx/decoder_model_merged_quantized.onnx": "0b009dc2d71add45954b927ff01815d25d9d397bbb8b2ad72c6b9bd3279d7607",
    "Xenova/whisper-medium/config.json": "a9c2ef0290a8fa3d203231dd01a074891b7f595d5d305ead2aac8ac5e6e47105",
    "Xenova/whisper-medium/generation_config.json": "c57f39da43ff86f60451a1c978743ca48fd995ac5d7e3c3534f856d0bed57770",
    "Xenova/whisper-medium/preprocessor_config.json": "a6a76d28c93edb273669eb9e0b0636a2bddbb1272c3261e47b7ca6dfdbac1b8d",
    "Xenova/whisper-medium/tokenizer.json": "27fc476bfe7f17299480be2273fc0608e4d5a99aba2ab5dec5374b4482d1a566",
    "Xenova/whisper-medium/tokenizer_config.json": "2a4c4281cf9f51ac6ccc406fdc711a087afe6530f671fa7b80953edc498275ce",
    "Xenova/whisper-medium/onnx/encoder_model_quantized.onnx": "7d6b4a00e441271646327f8a71b6e1bd1a305013cd914b51ddd76919c59ee3af",
    "Xenova/whisper-medium/onnx/decoder_model_merged_quantized.onnx": "2cdd6d06ebdf9d993d21117bfeeb7e9b399521b7766d3df77c54a85d6dcf3c08",
    "onnx-community/whisper-large-v3-turbo/config.json": "35cd83669f75bc2867f3b3a4461850392d5e308cd6ea951c3700539883c28df1",
    "onnx-community/whisper-large-v3-turbo/generation_config.json": "16f95291d2f47c944d3c2b19390bba7965666555c1ea2a0bdc850d1fab45612f",
    "onnx-community/whisper-large-v3-turbo/preprocessor_config.json": "7ccc62c6f2765af1f3b46c00c9b5894426835a05021c8b9c01eecb6dfb542711",
    "onnx-community/whisper-large-v3-turbo/tokenizer.json": "6d8cbd7cd0d8d5815e478dac67b85a26bbe77c1f5e0c6d76d1ce2abc0e5f21ca",
    "onnx-community/whisper-large-v3-turbo/tokenizer_config.json": "844b642c73a91359722f47b35705f7174686df33d252695d8572cf9ac03a6389",
    "onnx-community/whisper-large-v3-turbo/onnx/encoder_model_quantized.onnx": "d2f853dc3254fdc0079f55dd4433ea716ac98ec5574d3b475f288f2a77cebba9",
    "onnx-community/whisper-large-v3-turbo/onnx/decoder_model_merged_quantized.onnx": "61481bd3be3a445d5a4b9070e8f8b2c6cc4fbbbbdc9f0e7ed048a132b8b84e0d",
}


def hub_fetch(model: str, path: str):
    parts = path.split("/")
    if model not in HUB_MODELS or any(part in ("", ".", "..") or "\\" in part for part in parts):
        return None
    expected = HUB_PINNED.get(f"{model}/{path}")
    if expected is None or model not in HUB_REVISIONS:
        return None
    target = HUB.joinpath(*model.split("/"), *parts)
    with _hub_lock:
        if target.is_file():
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".download")
        digest = hashlib.sha256()
        try:
            url = f"https://huggingface.co/{model}/resolve/{HUB_REVISIONS[model]}/{path}"
            with httpx.stream("GET", url, follow_redirects=True, timeout=120) as response:
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                written = 0
                with temporary.open("wb") as out:
                    for chunk in response.iter_bytes(1024 * 1024):
                        written += len(chunk)
                        if written > 1_000_000_000:
                            raise ValueError("Model file exceeds the download limit")
                        out.write(chunk)
                        digest.update(chunk)
            if digest.hexdigest() != expected:
                raise ValueError(f"Checksum mismatch for {model}/{path}")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


@router.get("/hub/{owner}/{name}/resolve/{revision}/{path:path}")
def hub_file(owner: str, name: str, revision: str, path: str):
    target = hub_fetch(f"{owner}/{name}", path) if revision == "main" else None
    if target is None:
        raise HTTPException(404, "No such model file")
    return FileResponse(target)


@router.post("/{model}/import", status_code=201)
def import_model(model: str, file: UploadFile):
    if model not in MODELS or file.filename not in MODELS[model]["files"]:
        raise HTTPException(422, "Choose a model file with the expected filename")
    ROOT.mkdir(parents=True, exist_ok=True)
    target = ROOT / file.filename
    temporary = target.with_suffix(target.suffix + ".upload")
    count = 0
    try:
        with temporary.open("wb") as out:
            while chunk := file.file.read(1024 * 1024):
                count += len(chunk)
                if count > 2_000_000_000:
                    raise HTTPException(413, "Model is too large")
                out.write(chunk)
        if count < 1024:
            raise HTTPException(422, "Model file is incomplete")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {"model": model, "ready": ready(model)}


# P8: pinned SHA-256 per file. A built-in file absent here is refused by download(); only a speech model the person
# added themselves (its own URL, "added") downloads unpinned, with its hash recorded beside it.
PINNED: dict[str, str] = {
    # SD Turbo at the revision in its URLs: Hugging Face's LFS SHA-256 for the ONNX files, the fetched file's hash for
    # the small ones (23 October 2026)
    "diffusion/sd-turbo/LICENSE": "60be11ed67b0840980a84926b826e08cd41cfddac28f78a93ed2f8021af42623",
    "diffusion/sd-turbo/model_index.json": "6957dc0b3fd7908e41aad5d1226fb8e57c986a2de3467948e7bd5c67bb737fe2",
    "diffusion/sd-turbo/scheduler/scheduler_config.json": "979f1cf4f8e8e3dc9566ab4b1ed14fb9be0b2b44ee9b5b7d073744e2a578d1cf",
    "diffusion/sd-turbo/tokenizer/merges.txt": "9fd691f7c8039210e0fced15865466c65820d09b63988b0174bfe25de299051a",
    "diffusion/sd-turbo/tokenizer/special_tokens_map.json": "c2d0fb8b86ad86b1f46134d4a5f93fd1e688c932a78efc8d149087c33a53ad06",
    "diffusion/sd-turbo/tokenizer/tokenizer_config.json": "516314ccab66918d7cb647480ac27abd3520d14e1e5825aac99f50c851c16071",
    "diffusion/sd-turbo/tokenizer/vocab.json": "e089ad92ba36837a0d31433e555c8f45fe601ab5c221d4f607ded32d9f7a4349",
    "diffusion/sd-turbo/text_encoder/model.onnx": "a0d07fcce1858783b635c4027a562c89690d7c9f3f36c6129f1aa35af380f3d8",
    "diffusion/sd-turbo/unet/model.onnx": "3b1170b54ca0ceafe1c709cd0268bd98892928e5589a7d72aec817669472beda",
    "diffusion/sd-turbo/vae_decoder/model.onnx": "8b5a9263fbd3ebd2647bae8e99cc99fdcff70a0b1b6a77ca7544c5f3e9e91649",
    # Silero VAD v6.2.3 (commit 5cd79456), the same bytes as silero_vad/data/silero_vad.onnx in the 6.2.3 wheel
    "silero_vad.onnx": "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3",
    # Krea 2's builds and its content filter: the SHA-256 Hugging Face records for each large file at the pinned
    # revision, and for each small one the hash of the file fetched on 27 September 2026
    "krea-2-mlx-q8/.DS_Store": "bb49144c3319391c31ee22524247e886d795c3841d431559557dd3353cf13c29",
    "krea-2-mlx-q8/0.safetensors": "7dac52a29577e965460d4bea51f2b3b5b840e3d784715b2c590f810e4248681a",
    "krea-2-mlx-q8/1.safetensors": "471a58de454f7a04ff9b0ab0f28dbc27900d924d028d336dae92768244be6536",
    "krea-2-mlx-q8/2.safetensors": "b09c1671a3e966cf25eab5c9e464d1dc14b50ba1ecf14b5e9a98c0b1a838f900",
    "krea-2-mlx-q8/3.safetensors": "4318c7d38b17add1b2aacaf1422079c89d63a3d27c67a6bd37af4838727b9cec",
    "krea-2-mlx-q8/4.safetensors": "05c956017ba0dd6bc8c5e582fb867188404608c8660dc7271ab6d8d89c4a6c70",
    "krea-2-mlx-q8/5.safetensors": "6e39d518ec0179ec9aa60bbb5e9452e80624ea3b598c505b516868c756e27ef6",
    "krea-2-mlx-q8/6.safetensors": "2bbb8f18ea9387e2061308e134a08f028027a8216d21d7cd897fc03855f72651",
    "krea-2-mlx-q8/model.safetensors.index.json": "92539c59eab012cb7488fede1ff357edbf5c1245ea65efe875292908a2e4b782",
    "krea-2-mlx-q8/text_encoder/0.safetensors": "6dd135c977fd4a752c53ca06fd9d65ac1a6891a8771a8d65608a7728f2e3b560",
    "krea-2-mlx-q8/text_encoder/1.safetensors": "3b4a1c79423cd2a07bfafece4f542e1660133d66bee7985c09fa0939636675e3",
    "krea-2-mlx-q8/text_encoder/2.safetensors": "bfc931672551062f3f7b66e0c94b779cfa52c499991764d819093329071b4469",
    "krea-2-mlx-q8/text_encoder/3.safetensors": "88996823c97130307ff00b13291782bb26d25bbfd16f0c148249149a96a433b1",
    "krea-2-mlx-q8/text_encoder/model.safetensors.index.json": "79b7c1e303763dec75afa890bd20cfb40c0f0445be3e52e85dda1eac66cac3b5",
    "krea-2-mlx-q8/tokenizer/chat_template.jinja": "3636d0f0bd6bef02654cdffdc447b79cb2cef8ab02cc75267345946291a489e4",
    "krea-2-mlx-q8/tokenizer/tokenizer.json": "be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506",
    "krea-2-mlx-q8/tokenizer/tokenizer_config.json": "c871ed314285a377eccf509b906aa5fe015d5e79a3ddab2c198467329127ead6",
    "krea-2-mlx-q8/vae/0.safetensors": "3bc6157dec03fa1b8be8a97efcf6b3fe19d43b4210d369648b4efb0cc940a74c",
    "krea-2-mlx-q8/vae/model.safetensors.index.json": "a5c2f350d7b28c10b45ad16e27320021daf190b30af665b52bbe0288ad814be4",
    "krea-2-mlx-q4/.DS_Store": "fbf84581e26de02330c770e58e34fb36058b753a12c0a2080d129f84e5c8e79c",
    "krea-2-mlx-q4/0.safetensors": "294800e65afa7d727ef1a1402dfea86fd22c55e15a7631cce63ec84774041582",
    "krea-2-mlx-q4/1.safetensors": "ebeba87f73c97778a8975a72f15a8349d4483117d41fa7733da724bf4f7fe6b7",
    "krea-2-mlx-q4/2.safetensors": "30a895386a1fc4159402a24353d69195b87d30904149edaabb9ccae7aab7bf15",
    "krea-2-mlx-q4/3.safetensors": "c324675dced018804b17c41a52a99bb1ff4edd8836b44c610edf5de7cd475ded",
    "krea-2-mlx-q4/model.safetensors.index.json": "0143fce31bfab0d961b52d4690ee4ba6f8cd76cb0a2e04b38f78aeebe2e4e35f",
    "krea-2-mlx-q4/text_encoder/0.safetensors": "4e21e461e115028423a7a7665e3dd9e20c9b2bb3f40e2ee8e213c5fe0bc3d228",
    "krea-2-mlx-q4/text_encoder/1.safetensors": "83c768a56e0d48a47caa62f30dbf6c01d70f20ae22c4f71b7840b0856f91ccc9",
    "krea-2-mlx-q4/text_encoder/2.safetensors": "a03ee8c0084b129dcdedb91fe9295c18c0c8217003c6c5913c04156e82df5712",
    "krea-2-mlx-q4/text_encoder/3.safetensors": "2c274cc1b13f538583999bcb27d322b850109a385e76442575afc692a5832b75",
    "krea-2-mlx-q4/text_encoder/model.safetensors.index.json": "e5173ccee30fc4a6d3522e599196ba9e6470c6cbed9d10c59122d55c48106256",
    "krea-2-mlx-q4/tokenizer/chat_template.jinja": "3636d0f0bd6bef02654cdffdc447b79cb2cef8ab02cc75267345946291a489e4",
    "krea-2-mlx-q4/tokenizer/tokenizer.json": "be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506",
    "krea-2-mlx-q4/tokenizer/tokenizer_config.json": "c871ed314285a377eccf509b906aa5fe015d5e79a3ddab2c198467329127ead6",
    "krea-2-mlx-q4/vae/0.safetensors": "b2002a24b9a8227646065a1bd169729968402bda24d83b86fb8981124d324e76",
    "krea-2-mlx-q4/vae/model.safetensors.index.json": "a60148f10bc24b11909537ea960281eaf16a7ee066f2fe2988607dca62fdd5af",
    "krea-2-sdnq-int8/LICENSE.pdf": "b82a2805162bde714a4eb27b9063c4fc3345d08a30be055134a6160e5430ba74",
    "krea-2-sdnq-int8/model_index.json": "7d6c1206e369286df31244670a9a38fc73b077d8f64b4d273abb20ef9a8a8b93",
    "krea-2-sdnq-int8/scheduler/scheduler_config.json": "4d8ea4471195528cdb84fcb8d37cd54ff442b9c02ff74f7d16d0a7a2f14b9467",
    "krea-2-sdnq-int8/text_encoder/config.json": "d85211fccf7d376e1cdd77002464cf34cfce71e990147c8388fa643180e1a7e3",
    "krea-2-sdnq-int8/text_encoder/model.safetensors": "37cae4588e10f282e592dc49fb9944ff09fab5447ce3f705c5451d953b39fa1e",
    "krea-2-sdnq-int8/tokenizer/chat_template.jinja": "3636d0f0bd6bef02654cdffdc447b79cb2cef8ab02cc75267345946291a489e4",
    "krea-2-sdnq-int8/tokenizer/tokenizer.json": "be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506",
    "krea-2-sdnq-int8/tokenizer/tokenizer_config.json": "c871ed314285a377eccf509b906aa5fe015d5e79a3ddab2c198467329127ead6",
    "krea-2-sdnq-int8/transformer/config.json": "ac5512b2d684ce619a9500c87158e48712e53bfe1f8fda98be5dc57814b76af0",
    "krea-2-sdnq-int8/transformer/diffusion_pytorch_model-00001-of-00002.safetensors": "4451519f43f91a081fd7d9d881e6c4245759b71cdfa01f8ae9d371e75191c55a",
    "krea-2-sdnq-int8/transformer/diffusion_pytorch_model-00002-of-00002.safetensors": "7060caf00f7b4c724505d9945b1c79ef6fd861ad07dcdea4e06b299a14a6482f",
    "krea-2-sdnq-int8/transformer/diffusion_pytorch_model.safetensors.index.json": "aafab68d94c49ea754bb0dd92870ff93889d64933cdcb72be1a2e68447c4293b",
    "krea-2-sdnq-int8/vae/config.json": "54949c79def0d1060353c3fbfd4d2d2c4815ae241da6d6d28c99634c4eac6e6e",
    "krea-2-sdnq-int8/vae/diffusion_pytorch_model.safetensors": "ab1b61103959913d6c7e628cf793dbb2ca4726a40a3b3ae206c52b8e75bf6f08",
    "nsfw-filter/config.json": "0e01783cf842a0acaa6b3b6594b941bee4d39a1918756b27d23f503878889696",
    "nsfw-filter/onnx/model.onnx": "a4316a4fb750169ac4fcabaabee1fcbd982b0ee8c0cc63fe3e944954bb9a7d9c",
    "nsfw-filter/preprocessor_config.json": "ae9bb157b9629887cc74913a4e7c12c9308f374f0930e8072320e8f2e1583c5e",
    "nsfw-filter/quantize_config.json": "9b60b5877b9a1687b5cddbc06124a974cb7536af9dbf5295279bf73c3823170c",
    # BG1's gate, completed at v1.58.0: every registry file pinned to the
    # SHA-256 of the file actually fetched and hashed, matching the table in
    # .docs/wiki/Licences.md. A download that does not match never lands.
    "rvm_mobilenetv3_fp32.onnx": "88d4531297118f595bf2fd60f6f566aec2e559393802d1f436c380f0cbbd2828",
    "isnet-general-use.onnx": "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a",
    "sam2_hiera_tiny.encoder.onnx": "4cc015ee18520e93f8c7ddfeaca7436039daaaaf19721b4b96a8810a805e82f7",
    "sam2_hiera_tiny.decoder.onnx": "f5a4bd656c143899fb7f52d64ed81e6f6aeb37d477a0b6da50146ac7cf2187bf",
    "sam21-video-vision_encoder.onnx": "aa7a8542942f042e235a993a1ab0ccf5f049918500577802a7f10ec1b39bb873",
    "sam21-video-mask_decoder.onnx": "0461896de3db00936fe1643506f129d71cb6d5d2ae15754811756b7ea1b070c6",
    "sam21-video-memory_encoder.onnx": "580d246c109de88838f600ba7c1c0d03d1fe267f7641b06f8c88c5f0dc5834cd",
    "sam21-video-memory_attention.onnx": "791e648ce8f5ef91ad00ba06e83066ff261ae5a645f0b042b4f46a89fd054baf",
    "sam21-video-pointer_tpos.onnx": "7e71df1d75dba09bc18dd4ae745c2a2cceebdd14d84eadea2fe65d0205f101fc",
    "sam21-video-constants.json": "172edc70e892aab0aef6caedf97b8e4091fbf6c5d26dac5fd9ea69d093d927d3",
    "u2netp.onnx": "309c8469258dda742793dce0ebea8e6dd393174f89934733ecc8b14c76f4ddd8",
    "u2net_human_seg.onnx": "01eb6a29a5c4d8edb30b56adad9bb3a2a0535338e480724a213e0acfd2d1c73c",
    "realesrgan-x4plus.onnx": "4851ec156207d271f5328605d0582eeb851e656227da8aca093ced9e60789291",
    "kokoro-v1.0.onnx": "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
    "flux2-klein-4b-mlx-q8/text_encoder/0.safetensors": "c59037293e62b9142e06e602a03b734fdf7f0f6b80141759f875200bab5ff523",
    "flux2-klein-4b-mlx-q8/text_encoder/1.safetensors": "ccb1fd9fa0e19db71c44b3fdd9ed16e15dc14de3dcd240a0b162c4a10faba2cc",
    "flux2-klein-4b-mlx-q8/text_encoder/model.safetensors.index.json": "3273ab420ba8b5bfd991cc233b8d90afa794ffe856925299c892ee4c9d1614f2",
    "flux2-klein-4b-mlx-q8/tokenizer/chat_template.jinja": "a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8",
    "flux2-klein-4b-mlx-q8/tokenizer/tokenizer.json": "be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506",
    "flux2-klein-4b-mlx-q8/tokenizer/tokenizer_config.json": "779410a34a98fb2c6c925a1be6f24d632f1723473161b037f6676eb6c04886c6",
    "flux2-klein-4b-mlx-q8/transformer/0.safetensors": "442cb6770b834cb47043ef96f929b05b21e84bb1cca6daa806bf416aaa0b04f9",
    "flux2-klein-4b-mlx-q8/transformer/1.safetensors": "5cbf48740f8655185b3578a25188d2db72148ea2476385979961d89ee56d0dcc",
    "flux2-klein-4b-mlx-q8/transformer/model.safetensors.index.json": "fce32043337212c1fb02f5da46b0dde35cfecdb577d618e46bab6ce70392468f",
    "flux2-klein-4b-mlx-q8/vae/0.safetensors": "fc2ff418c22e76c8ad93c43b4ffdee19d10a90898d3d10ef3c53dda9ad9cb4f2",
    "flux2-klein-4b-mlx-q8/vae/model.safetensors.index.json": "ae30aec3a3da440b700726376c89d1574cb4182e4ca534809243606df4d3be38",
    "flux2-klein-4b-mlx-q4/text_encoder/0.safetensors": "e59ed2b6825cb8ae3d0ba1e8a43575a565d465ce4518b7d79d28020b19b639cd",
    "flux2-klein-4b-mlx-q4/text_encoder/1.safetensors": "edbdea3187bc4a0ad0e1ecb7152da8e6b344669413d9e45be5e7a2244f398ee3",
    "flux2-klein-4b-mlx-q4/text_encoder/model.safetensors.index.json": "7dc8598806b8bbdb0b87b9dc445ac7cf49d7acc42ae333bd0bc0252e46081ed9",
    "flux2-klein-4b-mlx-q4/tokenizer/chat_template.jinja": "a55ee1b1660128b7098723e0abcd92caa0788061051c62d51cbe87d9cf1974d8",
    "flux2-klein-4b-mlx-q4/tokenizer/tokenizer.json": "be75606093db2094d7cd20f3c2f385c212750648bd6ea4fb2bf507a6a4c55506",
    "flux2-klein-4b-mlx-q4/tokenizer/tokenizer_config.json": "779410a34a98fb2c6c925a1be6f24d632f1723473161b037f6676eb6c04886c6",
    "flux2-klein-4b-mlx-q4/transformer/0.safetensors": "36796395e3946496f3e118f26fe22594b1d7d871342a59dd7824349d91c08266",
    "flux2-klein-4b-mlx-q4/transformer/1.safetensors": "9730ae148ca4f5ffc62860748b849a70987f0b7301588248bd98a2af9bc15070",
    "flux2-klein-4b-mlx-q4/transformer/model.safetensors.index.json": "dbdecbf3a957b37d15bd943b956dbb25aa648a01df363e7dd5ebbe5ce941358d",
    "flux2-klein-4b-mlx-q4/vae/0.safetensors": "688ae0c3d2e93573ce8a6d3561d793cf6de5a4207b2e128cad6cd0d71e43b10f",
    "flux2-klein-4b-mlx-q4/vae/model.safetensors.index.json": "e13e551dabf8c088c8b3c6f52fca3f9e64ead5c42dd592586c7a1f868607afa4",
}

SOURCES_FILE = ROOT / "sources.json"


def _sources() -> dict:
    if SOURCES_FILE.is_file():
        try:
            return json.loads(SOURCES_FILE.read_text())
        except ValueError:
            return {}
    return {}


def source_for(model: str, name: str, default: str) -> str:
    """The URL to fetch a model file from: upstream, a mirror, or a custom URL."""
    chosen = _sources().get(model) or {}
    if isinstance(chosen, dict):
        if chosen.get("mode") == "custom" and chosen.get("url"):
            # A custom source is the exact URL the user gave; only a mirror is
            # treated as a base that the file name is appended to.
            return str(chosen["url"])
        if chosen.get("mode") == "mirror" and chosen.get("url"):
            return f"{str(chosen['url']).rstrip('/')}/{name}"
    return default


def set_source(model: str, mode: str, url: str | None) -> dict:
    """Record where a model should be fetched from."""
    if model not in MODELS:
        raise ValueError("Unknown model")
    if mode not in ("upstream", "mirror", "custom"):
        raise ValueError("Unknown source mode")
    if mode != "upstream" and not url:
        raise ValueError("A mirror or custom source needs a URL")
    ROOT.mkdir(parents=True, exist_ok=True)
    data = _sources()
    data[model] = {"mode": mode, "url": url}
    SOURCES_FILE.write_text(json.dumps(data, indent=2))
    return data[model]


def pin_for(name: str) -> str | None:
    return PINNED.get(name)


# Local speech is not one model. A person may add another ONNX voice model and
# its voices file, which is registered beside Kokoro and listed like it; the
# entry lives in the data directory so it survives an update of the app.
SPEECH_FILE = ROOT / "speech-models.json"


class SpeechModelInput(BaseModel):
    id: str = Field(min_length=2, max_length=48, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=80)
    model_url: str = Field(min_length=8, max_length=2000)
    voices_url: str | None = None
    license: str = "unknown"


def _speech_extra() -> dict:
    if SPEECH_FILE.is_file():
        try:
            return json.loads(SPEECH_FILE.read_text())
        except ValueError:
            return {}
    return {}


def load_speech_models() -> None:
    """Merge any added speech models into the registry at start."""
    for key, entry in _speech_extra().items():
        MODELS.setdefault(key, entry)


@router.get("/speech")
def list_speech_models() -> dict:
    return {"models": [{"id": key, **entry} for key, entry in _speech_extra().items()], "builtIn": "local-speech"}


@router.post("/speech", status_code=201)
def add_speech_model(body: SpeechModelInput) -> dict:
    key = f"speech-{body.id}"
    if key in MODELS and key not in _speech_extra():
        raise HTTPException(409, "That id is already used by a built-in model")
    files = {f"{body.id}.onnx": body.model_url}
    if body.voices_url:
        files[f"{body.id}-voices.bin"] = body.voices_url
    entry = {"name": body.name, "license": body.license, "files": files, "kind": "speech", "added": True}
    ROOT.mkdir(parents=True, exist_ok=True)
    data = _speech_extra()
    data[key] = entry
    SPEECH_FILE.write_text(json.dumps(data, indent=2))
    MODELS[key] = entry
    return {"id": key, **entry}


@router.delete("/speech/{key}", status_code=204)
def remove_speech_model(key: str) -> None:
    data = _speech_extra()
    if key not in data:
        raise HTTPException(404, "Unknown speech model")
    for name in data[key].get("files", {}):
        (ROOT / name).unlink(missing_ok=True)
        (ROOT / (name + ".json")).unlink(missing_ok=True)
    data.pop(key)
    SPEECH_FILE.write_text(json.dumps(data, indent=2))
    MODELS.pop(key, None)


load_speech_models()
