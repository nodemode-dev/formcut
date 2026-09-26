"""Local image generation through the engine's own ONNX Runtime.

A local model is a folder in the diffusers layout as the ONNX exports ship it:
text_encoder/model.onnx, unet/model.onnx, vae_decoder/model.onnx, the CLIP
tokenizer's vocab.json and merges.txt, and scheduler/scheduler_config.json.
This module carries the three pieces such a folder does not: the CLIP
byte-pair tokenizer, the Euler discrete scheduler (the one sd-turbo ships and
the one every SD 1.x and 2.x folder can run), and the loop. Which model to
put in that folder is the owner's decision and the registry's job; nothing
here downloads a model or names one, and a folder that is not there answers
"no local model" rather than fetching one.
"""

import json
import math
import re
import threading
import time
from pathlib import Path

import numpy as np

from .model_manager import providers
from .paths import MODELS_DIR

# The same models root the model manager downloads into, so a pinned model
# (local-image) and a folder a person drops in are found in one place.
MODELS = MODELS_DIR / "diffusion"
_lock = threading.Lock()
_loaded: dict = {}


class ClipTokenizer:
    """The CLIP BPE tokenizer, the encoding half, from vocab.json and merges.txt."""

    def __init__(self, folder: Path):
        self.encoder = json.loads((folder / "vocab.json").read_text(encoding="utf-8"))
        merges = (folder / "merges.txt").read_text(encoding="utf-8").splitlines()[1:]
        self.ranks = {tuple(line.split()): i for i, line in enumerate(merges) if line.strip()}
        printable = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
        mapped = list(printable)
        extra = 0
        for byte in range(256):
            if byte not in printable:
                printable.append(byte)
                mapped.append(256 + extra)
                extra += 1
        self.byte_encoder = {b: chr(m) for b, m in zip(printable, mapped, strict=True)}
        self.start = self.encoder.get("<|startoftext|>", 49406)
        self.end = self.encoder.get("<|endoftext|>", 49407)
        self.cache: dict = {}
        # CLIP's word pattern, with letter and digit classes the re module has.
        self.pattern = re.compile(r"'s|'t|'re|'ve|'m|'ll|'d|[a-zA-Z\u00C0-\uFFFF]+|[0-9]|[^\sa-zA-Z0-9\u00C0-\uFFFF]+", re.IGNORECASE)

    def bpe(self, token: str) -> list[str]:
        if token in self.cache:
            return self.cache[token]
        word = [*token[:-1], token[-1] + "</w>"]
        while len(word) > 1:
            pairs = [(word[i], word[i + 1]) for i in range(len(word) - 1)]
            best = min(pairs, key=lambda pair: self.ranks.get(pair, math.inf))
            if best not in self.ranks:
                break
            merged = []
            i = 0
            while i < len(word):
                if i < len(word) - 1 and (word[i], word[i + 1]) == best:
                    merged.append(word[i] + word[i + 1])
                    i += 2
                else:
                    merged.append(word[i])
                    i += 1
            word = merged
        self.cache[token] = word
        return word

    def encode(self, text: str, length: int = 77) -> np.ndarray:
        text = re.sub(r"\s+", " ", text.strip().lower())
        ids = [self.start]
        for piece in self.pattern.findall(text):
            mapped = "".join(self.byte_encoder[b] for b in piece.encode("utf-8"))
            ids.extend(self.encoder.get(part, self.end) for part in self.bpe(mapped))
        ids = [*ids[: length - 1], self.end]
        ids += [self.end] * (length - len(ids))
        return np.array([ids], np.int64)


class EulerScheduler:
    """Euler discrete, epsilon prediction, trailing spacing: sd-turbo's scheduler and a fit for SD 1.x and 2.x."""

    def __init__(self, config: dict, steps: int):
        train = int(config.get("num_train_timesteps", 1000))
        start, end = float(config.get("beta_start", 0.00085)), float(config.get("beta_end", 0.012))
        betas = (
            np.linspace(start**0.5, end**0.5, train, dtype=np.float64) ** 2
            if config.get("beta_schedule", "scaled_linear") == "scaled_linear"
            else np.linspace(start, end, train, dtype=np.float64)
        )
        alphas = np.cumprod(1 - betas)
        sigmas = np.sqrt((1 - alphas) / alphas)
        self.prediction = config.get("prediction_type", "epsilon")
        steps = max(1, steps)
        if config.get("timestep_spacing", "trailing") == "trailing" or steps == 1:
            timesteps = np.round(np.arange(train, 0, -train / steps)).astype(np.int64) - 1
        else:
            timesteps = np.linspace(0, train - 1, steps, dtype=np.float64)[::-1].round().astype(np.int64)
        self.timesteps = timesteps
        self.sigmas = np.append(np.interp(timesteps, np.arange(train), sigmas), 0.0)
        self.init_noise_sigma = float(np.sqrt(self.sigmas[0] ** 2 + 1))

    def scale(self, sample: np.ndarray, index: int) -> np.ndarray:
        return sample / np.sqrt(self.sigmas[index] ** 2 + 1)

    def step(self, output: np.ndarray, index: int, sample: np.ndarray) -> np.ndarray:
        sigma = self.sigmas[index]
        if self.prediction == "v_prediction":
            denoised = output * (-sigma / np.sqrt(sigma**2 + 1)) + sample / (sigma**2 + 1)
        else:
            denoised = sample - sigma * output
        derivative = (sample - denoised) / sigma
        return sample + derivative * (self.sigmas[index + 1] - sigma)


class LocalDiffusion:
    """One model folder's sessions and configs, held for the next request."""

    def __init__(self, folder: Path):
        import onnxruntime as ort

        options = ort.SessionOptions()
        options.log_severity_level = 3
        chosen = providers()
        self.folder = folder
        self.name = folder.name
        self.tokenizer = ClipTokenizer(folder / "tokenizer")
        self.text_encoder = ort.InferenceSession(str(folder / "text_encoder" / "model.onnx"), options, providers=chosen)
        self.unet = ort.InferenceSession(str(folder / "unet" / "model.onnx"), options, providers=chosen)
        self.vae = ort.InferenceSession(str(folder / "vae_decoder" / "model.onnx"), options, providers=chosen)
        self.provider = self.unet.get_providers()[0]
        self.scheduler_config = json.loads((folder / "scheduler" / "scheduler_config.json").read_text(encoding="utf-8"))
        vae_config = folder / "vae_decoder" / "config.json"
        self.scaling = float(json.loads(vae_config.read_text()).get("scaling_factor", 0.18215)) if vae_config.is_file() else 0.18215
        unet_config = folder / "unet" / "config.json"
        self.sample_size = int(json.loads(unet_config.read_text()).get("sample_size", 64)) if unet_config.is_file() else 64
        self.timestep_type = next(i.type for i in self.unet.get_inputs() if i.name == "timestep")
        self.unet_inputs = {i.name for i in self.unet.get_inputs()}

    def generate(
        self,
        prompt: str,
        negative: str = "",
        steps: int = 4,
        guidance: float = 0.0,
        width: int = 512,
        height: int = 512,
        seed: int | None = None,
        report=lambda f: None,
        cancelled=lambda: False,
    ) -> np.ndarray:
        """An RGB uint8 picture; guidance 0 means one UNet pass per step, which is how sd-turbo is meant to run."""
        width, height = max(64, (width // 8) * 8), max(64, (height // 8) * 8)
        tokens = self.tokenizer.encode(prompt)
        embeddings = self.text_encoder.run(None, {"input_ids": tokens})[0]
        classifier_free = guidance > 1.0
        if classifier_free:
            uncond = self.text_encoder.run(None, {"input_ids": self.tokenizer.encode(negative)})[0]
            embeddings = np.concatenate([uncond, embeddings], axis=0)
        scheduler = EulerScheduler(self.scheduler_config, steps)
        rng = np.random.default_rng(seed)
        latents = rng.standard_normal((1, 4, height // 8, width // 8)).astype(np.float32) * scheduler.init_noise_sigma
        dtype = np.float16 if "float16" in self.timestep_type else (np.int64 if "int64" in self.timestep_type else np.float32)
        for index, timestep in enumerate(scheduler.timesteps):
            if cancelled():
                raise InterruptedError("Cancelled")
            scaled = scheduler.scale(latents, index).astype(np.float32)
            sample = np.concatenate([scaled, scaled], axis=0) if classifier_free else scaled
            feeds = {"sample": sample, "timestep": np.array(timestep, dtype), "encoder_hidden_states": embeddings.astype(np.float32)}
            if "timestep_cond" in self.unet_inputs:
                feeds["timestep_cond"] = np.zeros((sample.shape[0], 256), np.float32)
            output = self.unet.run(None, feeds)[0].astype(np.float32)
            if classifier_free:
                uncond_out, text_out = output[:1], output[1:]
                output = uncond_out + guidance * (text_out - uncond_out)
            latents = scheduler.step(output, index, latents).astype(np.float32)
            report((index + 1) / (len(scheduler.timesteps) + 1))
        picture = self.vae.run(None, {"latent_sample": (latents / self.scaling).astype(np.float32)})[0][0]
        picture = np.clip((picture.transpose(1, 2, 0) + 1) / 2, 0, 1)
        report(1.0)
        return (picture * 255 + 0.5).astype(np.uint8)


PARTS = (
    "text_encoder/model.onnx",
    "unet/model.onnx",
    "vae_decoder/model.onnx",
    "tokenizer/vocab.json",
    "tokenizer/merges.txt",
    "scheduler/scheduler_config.json",
)


def installed() -> list[dict]:
    """The model folders present: the diffusers layout under the data directory's models/diffusion."""
    found = []
    if MODELS.is_dir():
        for folder in sorted(p for p in MODELS.iterdir() if p.is_dir()):
            complete = all((folder / part).is_file() for part in PARTS)
            licence = folder / "LICENSE"
            excerpt = licence.read_text(encoding="utf-8", errors="replace")[:200].strip() if licence.is_file() else None
            found.append({"id": folder.name, "complete": complete, "licence": excerpt})
    return found


def load(name: str) -> LocalDiffusion:
    with _lock:
        if name in _loaded:
            return _loaded[name]
    folder = MODELS / name
    if not folder.is_dir() or "/" in name or ".." in name:
        raise ValueError(f"No local model named {name}; put a diffusers-layout ONNX folder at {MODELS / name}")
    model = LocalDiffusion(folder)
    with _lock:
        _loaded.clear()
        _loaded[name] = model
    return model


def generate_to_file(name: str, prompt: str, path: Path, **options) -> dict:
    """Generate and write a PNG; the timing goes back with the result so the number is on the record."""
    from PIL import Image

    started = time.time()
    model = load(name)
    picture = model.generate(prompt, **options)
    Image.fromarray(picture).save(path, format="PNG")
    return {
        "path": str(path),
        "model": name,
        "provider": model.provider,
        "seconds": round(time.time() - started, 1),
        "width": int(picture.shape[1]),
        "height": int(picture.shape[0]),
    }
