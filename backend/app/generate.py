"""Generative media (image, video, audio).

Generation goes through the same provider registry that stock and speech use,
so a key is stored once and the engine never puts it in a document or a log.
Every provider is declared as data: which purposes it serves, what it needs and
what it returns, so the interface can build its own controls from the reply
rather than hard-coding a vendor.

A request for a provider with no key gets a clear, actionable refusal rather
than a failed network call, which is the difference between "add a key in
Settings" and a stack trace.
"""

from __future__ import annotations

import base64
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import jobs
from .media import ingest_path
from .paths import DATA_DIR
from .providers import PROVIDERS, base_for, key_for

router = APIRouter(prefix="/api/generate", tags=["generate"])

STAGING = DATA_DIR / "generated"

# Each entry says what the interface should offer. Sizes and durations are the
# provider's own, so the sheet cannot offer a shape the provider will refuse.
GENERATORS: dict[str, dict] = {
    # fal.ai is the one cloud generator. Each entry is a fal model slot; the
    # model id is an option, so another fal model is one line in this table or
    # a different id typed into the request, not a new provider.
    "fal-image": {
        "label": "fal.ai image (FLUX schnell)",
        "provider": "fal",
        "kind": "image",
        "sizes": ["1024x1024", "1344x768", "768x1344"],
        "options": {
            "model": "fal-ai/flux/schnell",
            "steps": {"min": 1, "max": 12, "default": 4},
            "count": {"min": 1, "max": 4, "default": 1},
        },
        "path": "/fal-ai/flux/schnell",
    },
    "fal-video": {
        "label": "fal.ai video (LTX)",
        "provider": "fal",
        "kind": "video",
        "sizes": ["1280x720", "720x1280"],
        "options": {"model": "fal-ai/ltx-video", "seconds": {"min": 2, "max": 10, "default": 5}},
        "path": "/fal-ai/ltx-video",
    },
    "fal-image-to-video": {
        "label": "fal.ai image to video (LTX)",
        "provider": "fal",
        "kind": "video",
        "sizes": ["1280x720", "720x1280"],
        "options": {"model": "fal-ai/ltx-video/image-to-video", "seconds": {"min": 2, "max": 10, "default": 5}, "image_url": ""},
        "path": "/fal-ai/ltx-video/image-to-video",
    },
    "elevenlabs-sound": {
        "label": "ElevenLabs sound effects",
        "provider": "elevenlabs",
        "kind": "audio",
        "sizes": [],
        "options": {"seconds": {"min": 1, "max": 22, "default": 6}, "influence": {"min": 0, "max": 1, "default": 0.3}},
        "path": "/v1/sound-generation",
    },
}

# Providers the generators need that the registry did not already carry.
EXTRA_PROVIDERS = {
    "fal": {
        "label": "fal.ai",
        "env": "FAL_KEY",
        "base_env": "FAL_BASE",
        "base": "https://fal.run",
        "purpose": "generate",
    },
}
for _name, _entry in EXTRA_PROVIDERS.items():
    PROVIDERS.setdefault(_name, _entry)


class GenerateBody(BaseModel):
    generator: str
    prompt: str = Field(min_length=1, max_length=2000)
    negative: str = ""
    size: str | None = None
    seconds: float | None = None
    count: int = 1
    options: dict = {}


def catalogue() -> list[dict]:
    """What the interface may offer, with each entry's readiness."""
    out = []
    for key, entry in GENERATORS.items():
        provider = entry["provider"]
        out.append(
            {
                "id": key,
                "label": entry["label"],
                "kind": entry["kind"],
                "provider": provider,
                "providerLabel": PROVIDERS.get(provider, {}).get("label", provider),
                "sizes": entry["sizes"],
                "options": entry["options"],
                "ready": bool(key_for(provider)),
            }
        )
    # Local models: the slots declared in models/local_models.json (image or
    # video, over the ONNX diffusion runner or a command of the person's own)
    # and any undeclared diffusion folder; run in the engine, no key.
    from .local_models import catalogue_entries

    out.extend(catalogue_entries())
    return out


@router.get("")
def list_generators() -> dict:
    return {"generators": catalogue()}


def _payload(entry: dict, body: GenerateBody) -> tuple[dict, dict]:
    """The request body and headers for one provider, kept in one place."""
    key = key_for(entry["provider"])
    size = body.size or (entry["sizes"][0] if entry["sizes"] else None)
    if entry["provider"] == "fal":
        # fal.run/<model id>: one synchronous call, JSON in, JSON with URLs out.
        width, _, height = (size or "1024x1024").partition("x")
        payload: dict = {"prompt": body.prompt}
        if body.negative:
            payload["negative_prompt"] = body.negative
        if entry["kind"] == "image":
            payload["image_size"] = {"width": int(width), "height": int(height)}
            payload["num_images"] = max(1, min(4, body.count))
            payload["num_inference_steps"] = int(body.options.get("steps", entry["options"].get("steps", {}).get("default", 4)))
        else:
            payload["aspect_ratio"] = "16:9" if int(width) >= int(height) else "9:16"
            payload["duration"] = float(body.seconds or entry["options"].get("seconds", {}).get("default", 5))
            if body.options.get("image_url"):
                payload["image_url"] = str(body.options["image_url"])
        if body.options.get("seed") is not None:
            payload["seed"] = int(body.options["seed"])
        return payload, {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    return (
        {"text": body.prompt, "duration_seconds": float(body.seconds or 6), "prompt_influence": float(body.options.get("influence", 0.3))},
        {"xi-api-key": key},
    )


def fal_path(entry: dict, body: GenerateBody) -> str:
    """The model id the request names, or the slot's own; a path under fal.run, never a URL of its own."""
    model = str(body.options.get("model") or entry["options"].get("model") or "").strip().strip("/")
    if not model or ".." in model or "://" in model:
        return entry["path"]
    return "/" + model


def _extract(entry: dict, response: httpx.Response) -> list[bytes]:
    """Bytes of whatever the provider returned, however it chose to return it."""
    media_type = response.headers.get("content-type", "")
    if not media_type.startswith("application/json"):
        return [response.content]
    data = response.json()
    out: list[bytes] = []
    for item in data.get("data") or data.get("artifacts") or data.get("images") or []:
        if isinstance(item, dict):
            encoded = item.get("b64_json") or item.get("base64") or item.get("image")
            if encoded:
                out.append(base64.b64decode(encoded))
            elif item.get("url"):
                out.append(httpx.get(item["url"], timeout=120, follow_redirects=True).content)
    if not out and isinstance(data.get("output"), str):
        out.append(httpx.get(data["output"], timeout=300, follow_redirects=True).content)
    video = data.get("video")
    if not out and isinstance(video, dict) and video.get("url"):
        out.append(httpx.get(video["url"], timeout=600, follow_redirects=True).content)
    if not out:
        raise ValueError("The provider returned nothing that could be read as media")
    return out


@router.post("", status_code=202)
def generate(body: GenerateBody):
    if body.generator.startswith("local:"):
        return _generate_local(body)
    entry = GENERATORS.get(body.generator)
    if not entry:
        raise HTTPException(404, "Unknown generator")
    if not key_for(entry["provider"]):
        label = PROVIDERS.get(entry["provider"], {}).get("label", entry["provider"])
        raise HTTPException(409, f"Add a {label} key in Settings before generating")

    def operation(job_id, report, cancelled):
        STAGING.mkdir(parents=True, exist_ok=True)
        payload, headers = _payload(entry, body)
        report(0.1)
        with httpx.Client(timeout=600, follow_redirects=True) as client:
            path = fal_path(entry, body) if entry["provider"] == "fal" else entry["path"]
            response = client.post(base_for(entry["provider"]).rstrip("/") + path, json=payload, headers=headers)
            if response.status_code >= 400:
                raise ValueError(f"{entry['label']} refused the request ({response.status_code}): {response.text[:300]}")
            report(0.6)
            blobs = _extract(entry, response)
        made = []
        for index, blob in enumerate(blobs):
            if cancelled():
                raise InterruptedError("Cancelled")
            suffix = {"image": ".png", "video": ".mp4", "audio": ".mp3"}[entry["kind"]]
            staged = STAGING / f"{uuid.uuid4().hex}{suffix}"
            staged.write_bytes(blob)
            try:
                made.append(
                    ingest_path(
                        staged,
                        f"{body.prompt[:48]} ({entry['label']})",
                        extra={"source": "generated", "generator": body.generator, "prompt": body.prompt},
                    )
                )
            finally:
                staged.unlink(missing_ok=True)
            report(0.6 + 0.4 * (index + 1) / len(blobs))
        return {"media": made, "kind": entry["kind"]}

    return jobs.submit("generate", operation)


def _size_of(size: str | None, largest: int = 1024) -> tuple[int, int]:
    """A WxH string clamped to 64..largest (1024, or 2048 for Krea 2), 512 square otherwise."""
    if size and "x" in size:
        parts = size.split("x", 1)
        if all(part.strip().isdigit() for part in parts):
            return max(64, min(largest, int(parts[0]))), max(64, min(largest, int(parts[1])))
    return 512, 512


IMAGE_STRENGTH = 0.4  # mflux's default for Krea 2's --image: how much the source picture shapes the result


def _source_image(spec: dict, into: Path) -> Path:
    """The picture image-to-image starts from, written as a PNG into the staging folder: an image in the media
    library, a video in it at a time, or the project's own frame at a time (rendered at full size, as an export)."""
    import numpy as np
    from PIL import Image

    from . import media

    out = into / f"source-{uuid.uuid4().hex}.png"
    into.mkdir(parents=True, exist_ok=True)
    if spec.get("mediaId"):
        item = media._find(str(spec["mediaId"]))
        matches = list(media.MEDIA_DIR.glob(f"{item['id']}.*"))
        if not matches:
            raise HTTPException(404, "that media file is missing")
        if item.get("kind") == "image":
            with Image.open(matches[0]) as picture:
                picture.convert("RGB").save(out)
            return out
        if item.get("kind") == "video":
            import cv2

            capture = cv2.VideoCapture(str(matches[0]))
            capture.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(spec.get("time") or 0)) * 1000)
            ok, frame = capture.read()
            capture.release()
            if not ok:
                raise HTTPException(400, "could not read that video at that time")
            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).save(out)
            return out
        raise HTTPException(400, "image-to-image starts from an image or a video's frame")
    if isinstance(spec.get("project"), dict):
        from .renderer import FrameRenderer

        renderer = FrameRenderer(spec["project"])
        try:
            pixels = np.asarray(renderer.frame(max(0.0, float(spec.get("time") or 0))))
        finally:
            close = getattr(renderer, "close", None)
            if close:
                close()
        Image.fromarray(pixels[..., :3].astype(np.uint8)).save(out)
        return out
    raise HTTPException(400, "give a media image, a media video and a time, or the project and a time to start from")


_SESSIONS: dict[str, Path] = {}  # continuous sessions: their job and the prompt file mflux reads before each seed


def _continuous(body, slot: dict, name: str, prompt: str, stack: list, sampling: dict, width: int, height: int, steps: int, notes: list):
    """Krea 2 (or a checkpoint) generating picture after picture with the model and its LoRAs loaded once, until
    cancelled: one mflux process over many random seeds (krea2.run_continuous). Each picture goes through the content
    filter, has its recipe written into it, joins the library, and is published on the job as it is made; the prompt
    can be changed between pictures (POST /api/generate/sessions/<job>/prompt)."""
    import time as clock

    from . import content_filter, krea2
    from .media import ingest_path

    checkpoint = Path(slot["checkpoint"]) if slot.get("checkpoint") else None
    memory = str(body.options.get("memory") or "auto")

    def operation(job_id, report, cancelled):
        STAGING.mkdir(parents=True, exist_ok=True)
        prompt_file = STAGING / f"prompt-{job_id}.txt"
        prompt_file.write_text(prompt, encoding="utf-8")
        _SESSIONS[job_id] = prompt_file
        made, seeds_used, session_notes = [], [], list(notes)
        last = {"time": clock.time()}
        state = krea2.policy()
        warning = None if state["filterInstalled"] or state.get("removalAcknowledged") else krea2.REMOVED_WARNING

        def on_picture(seed_value: int, path: Path) -> None:
            from PIL import Image

            seconds = round(clock.time() - last["time"], 1)
            last["time"] = clock.time()
            verdict = None
            if state["filterInstalled"]:
                import numpy as np

                verdict = content_filter.check(np.asarray(Image.open(path).convert("RGB")))
                if verdict["withheld"]:
                    path.unlink(missing_ok=True)
                    session_notes.append(f"seed {seed_value} withheld by the content filter, NSFW score {verdict['nsfw']:.2f}")
                    report(0.1, "Next picture", notes=list(session_notes))
                    return
            with Image.open(path) as picture:
                dims = picture.size
            current = prompt_file.read_text(encoding="utf-8")
            result = {"seed": seed_value, "width": dims[0], "height": dims[1], "seconds": seconds}
            recipe = _recipe(current, result, steps, stack, sampling, slot)
            _stamp(path, recipe["parameters"])
            try:
                item = ingest_path(
                    path,
                    f"{current[:48]} ({name}, local)",
                    extra={
                        "source": "generated",
                        "generator": body.generator,
                        "prompt": current,
                        "seconds": seconds,
                        "provider": f"Krea 2 checkpoint {checkpoint.name} (mflux)" if checkpoint else "Krea 2 (mflux, continuous)",
                        "notice": krea2.NOTICE,
                        "contentFilter": verdict or "removed",
                        **recipe,
                    },
                )
            finally:
                path.unlink(missing_ok=True)
            made.append(item)
            seeds_used.append(seed_value)
            report(
                0.1,
                f"Picture {len(made)} done in {seconds:g} s",
                made=list(made),
                seeds=list(seeds_used),
                notes=list(session_notes),
                warning=warning,
            )

        try:
            while not cancelled():
                # the seeds of one session run out after hundreds of pictures: the next session loads the model again
                krea2.run_continuous(
                    prompt_file,
                    STAGING,
                    on_picture,
                    width,
                    height,
                    steps=steps,
                    stack=stack,
                    memory=memory,
                    report=report,
                    cancelled=cancelled,
                    folder=checkpoint,
                    sampling=sampling,
                )
        finally:
            _SESSIONS.pop(job_id, None)
            prompt_file.unlink(missing_ok=True)
            if sampling.get("image"):
                Path(sampling["image"][0]).unlink(missing_ok=True)
        return {
            "media": made,
            "kind": "image",
            "seeds": seeds_used,
            "notes": session_notes,
            "model": slot.get("id", name),
            **({"warning": warning} if warning else {}),
        }

    return jobs.submit("generate", operation)


class SessionPrompt(BaseModel):
    prompt: str


@router.post("/sessions/{job_id}/prompt")
def change_session_prompt(job_id: str, body: SessionPrompt) -> dict:
    """A continuous session's prompt, changed between pictures: the next picture reads it. Its LoRAs, size and steps
    stay as the session started; a <lora:> tag is taken out, as the loaded LoRAs cannot change mid-session."""
    from . import krea2, prompt_data

    prompt_file = _SESSIONS.get(job_id)
    if prompt_file is None:
        raise HTTPException(404, "No continuous session by that id")
    text = prompt_data.parse(body.prompt)["prompt"] or body.prompt
    refusal = krea2.prompt_refusal(text)
    if refusal:
        raise HTTPException(400, refusal)
    prompt_file.write_text(text, encoding="utf-8")
    return {"prompt": text, "applies": "from the next picture"}


def _recipe(prompt: str, result: dict, steps: int, stack: list, sampling: dict, slot: dict) -> dict:
    """What made a picture: its seed and settings, and the "parameters" text Automatic1111 writes into a PNG, with the
    LoRAs as <lora:file:strength> tags so that the text, pasted back into the generator, makes the picture again."""
    from . import loras

    base = slot.get("base") or ("krea-2" if slot["runner"] == "krea-2" else slot["id"])
    library = {entry["id"]: entry for entry in loras.entries(base)}
    used = []
    for item in stack or []:
        entry = library.get(str(item.get("id")))
        if entry and item.get("enabled") is not False and float(item.get("scale", 1)) != 0:
            used.append((entry["file"].rsplit(".", 1)[0], float(item.get("scale", entry["scale"]))))
    tags = " ".join(f"<lora:{stem}:{scale:g}>" for stem, scale in used)
    guidance = float(sampling.get("guidance", 1.0)) if slot["runner"] == "krea-2" else 1.0
    scheduler = sampling.get("scheduler") or ("er_sde" if slot["runner"] == "krea-2" else "flow match euler")
    line = [
        f"Steps: {steps}",
        f"Sampler: {scheduler}",
        f"CFG scale: {guidance:g}",
        f"Seed: {result['seed']}",
        f"Size: {result.get('width')}x{result.get('height')}",
    ]
    # a checkpoint by its folder's name, a base model by its id: what the generator's Model reads back
    line.append(f"Model: {Path(slot['checkpoint']).name if slot.get('checkpoint') else base}")
    if sampling.get("image"):
        line.append(f"Denoising strength: {1 - float(sampling['image'][1]):g}")
    line.append("Version: formcut")
    text = prompt + (f"\n{tags}" if tags else "")
    if sampling.get("negative") and guidance != 1.0:
        text += f"\nNegative prompt: {sampling['negative']}"
    text += "\n" + ", ".join(line)
    return {
        "seed": result["seed"],
        "steps": steps,
        "width": result.get("width"),
        "height": result.get("height"),
        "loras": [{"file": stem, "scale": scale} for stem, scale in used],
        "sampler": scheduler,
        "guidance": guidance,
        **({"imageInfluence": float(sampling["image"][1])} if sampling.get("image") else {}),
        "parameters": text,
    }


def _stamp(path: Path, parameters: str) -> None:
    """The picture's "parameters" written into its PNG beside what is already there (mflux's own record included)."""
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    if path.suffix.lower() != ".png":
        return
    with Image.open(path) as picture:
        picture.load()
        info = PngInfo()
        for key, value in (getattr(picture, "text", None) or {}).items():
            if key != "parameters":
                info.add_text(key, str(value))
        info.add_text("parameters", parameters)
        picture.save(path, pnginfo=info)


def _fit(width: int, height: int, largest: int = 2048) -> tuple[int, int]:
    """A source picture's size within the model's largest side, in multiples of 16."""
    scale = min(1.0, largest / max(width, height))
    return max(256, int(width * scale) // 16 * 16), max(256, int(height * scale) // 16 * 16)


def _civitai_prompt(slot: dict, text: str, stack: list) -> tuple[dict, str, list, list, dict]:
    """<lora:name:strength> tags and Civitai's generation data, for Krea 2, Klein 4B and their checkpoints: the tags'
    LoRAs found in the library by file name (as Automatic1111 finds them) and put in the stack at their strengths,
    the parameters line's Steps, Seed and size used, its Model choosing a checkpoint of that name, and a note for what
    these models do not take (sampler, CFG other than 1, a negative prompt, clip skip)."""
    from . import checkpoints, loras, prompt_data
    from .local_models import resolve

    data = prompt_data.parse(text)
    params, notes, found = data["params"], [], {}
    base = slot.get("base") or ("krea-2" if slot["runner"] == "krea-2" else slot["id"])
    model = params.get("model")
    if model and model.lower() not in (base, slot.get("id", ""), "krea2", "krea-2", "flux2-klein-4b"):
        ckpt = checkpoints.find(base, model)
        if ckpt is not None and ckpt["id"] != slot.get("id"):
            chosen = resolve(ckpt["id"])
            if chosen is not None and chosen["ready"]:
                slot = chosen
                notes.append(f"Model {model}: the checkpoint in models/checkpoints/{base}/{ckpt['name']}")
        elif ckpt is None and slot.get("checkpoint") is None:
            notes.append(f"Model {model} is not in models/checkpoints/{base}/; made with {checkpoints.BASES[base]}")
    library = loras.entries(base)
    missing = []
    for tag, strength in data["loras"]:
        entry = prompt_data.match_lora(tag, library)
        if entry is None:
            missing.append(tag)
            continue
        stack = [item for item in stack if item.get("id") != entry["id"]] + [{"id": entry["id"], "scale": strength}]
    if missing:
        folder = loras.LIBRARY / base
        raise HTTPException(
            400,
            f"LoRA not found for {checkpoints.BASES[base]}: {', '.join(missing)}. Put the .safetensors in {folder} (its file name is what <lora:name> names), or add it from a link.",
        )
    if len(stack) > loras.MAX_STACK:
        raise HTTPException(400, f"up to {loras.MAX_STACK} LoRAs at once")
    if "steps" in params:
        found["steps"] = max(1, min(50, params["steps"]))
    if "seed" in params:
        found["seed"] = params["seed"] & 0xFFFFFFFF
    if "width" in params and "height" in params:
        found["width"] = max(256, min(2048, params["width"] // 16 * 16))
        found["height"] = max(256, min(2048, params["height"] // 16 * 16))
        if (found["width"], found["height"]) != (params["width"], params["height"]):
            notes.append(f"size {params['width']}x{params['height']} made {found['width']}x{found['height']} (a multiple of 16)")
    krea = slot["runner"] == "krea-2"
    if params.get("cfg") not in (None, 1.0):
        if krea:
            # Krea 2 takes CFG: any guidance but 1.0 turns it on (an extra pass a step, slower), with the negative prompt
            found["guidance"] = max(0.0, min(15.0, params["cfg"]))
            notes.append(f"CFG scale {params['cfg']:g}: CFG on, which takes longer")
        else:
            notes.append(f"CFG scale {params['cfg']:g} not used: FLUX.2 [klein] 4B is distilled to guidance 1.0")
    sampler = str(params.get("sampler") or "").lower()
    if sampler:
        if krea and "euler" in sampler:
            found["scheduler"] = "euler"
            notes.append(
                f"Sampler {params['sampler']}: mflux's euler" + (" (it has no ancestral Euler)" if sampler.startswith("euler a") else "")
            )
        elif krea and ("er_sde" in sampler or "er sde" in sampler):
            found["scheduler"] = "er_sde"
        else:
            notes.append(
                f"Sampler {params['sampler']} not used: "
                + ("Krea 2 has er_sde and euler" if krea else "mflux samples Klein with its own scheduler")
            )
    for key, label in (("schedule_type", "Schedule type"), ("clip_skip", "Clip skip")):
        if key in params and not (key == "clip_skip" and str(params[key]) == "1"):
            notes.append(f"{label} {params[key]} not used by mflux")
    if data["negative"]:
        if krea and found.get("guidance", 1.0) != 1.0:
            found["negative"] = data["negative"]
        else:
            notes.append("the negative prompt is not used: it takes CFG, a CFG scale other than 1" + ("" if krea else " (Krea 2 only)"))
    if data["loras"]:
        notes.append(f"LoRAs from the prompt: {', '.join(f'{name} {weight:g}' for name, weight in data['loras'])}")
    if "denoising_strength" in params:
        # A1111's img2img denoising is how much is repainted; mflux's strength how much the source is kept
        found["imageStrength"] = max(0.0, min(1.0, 1.0 - params["denoising_strength"]))
    return slot, data["prompt"] or text, stack, notes, found


def _generate_local(body: GenerateBody):
    """A local slot: the same job shape as a provider, run in the engine, one result per count."""
    from .local_diffusion import generate_to_file
    from .local_models import resolve, run_command_slot

    name = body.generator.split(":", 1)[1]
    slot = resolve(name)
    if slot is None:
        raise HTTPException(404, "No local model by that name")
    if not slot.get("ready", True):
        raise HTTPException(409, f"{name} is not ready: {slot.get('reason') or 'see models/local_models.json'}")
    width, height = _size_of(body.size, 2048 if slot["runner"] in ("krea-2", "mflux-klein") else 1024)
    steps = max(1, min(50, int(body.options.get("steps", slot.get("steps") if slot.get("steps") is not None else 4))))
    guidance = max(0.0, min(15.0, float(body.options.get("guidance", slot.get("guidance") if slot.get("guidance") is not None else 0.0))))
    seconds = float(body.seconds or slot.get("seconds") or 5)
    seed = body.options.get("seed")
    if seed is not None and int(seed) < 0:
        seed = None  # -1: a random seed, the one used reported with each picture
    count = max(1, min(4, body.count))
    kind = slot.get("kind", "image")
    extension = slot.get("extension") or (".mp4" if kind == "video" else ".png")
    # A prompt written as Civitai shows it: <lora:name:strength> tags and the generation data read into the request
    prompt, stack, notes, sampling = body.prompt, list(body.options.get("loras") or []), [], {}
    if slot["runner"] in ("krea-2", "mflux-klein"):
        slot, prompt, stack, notes, found = _civitai_prompt(slot, body.prompt, stack)
        # Krea 2's sampling, from the panel or the pasted generation data (which wins, as on Civitai)
        sampling = {key: body.options[key] for key in ("scheduler", "negative") if body.options.get(key)}
        if "guidance" in body.options:
            sampling["guidance"] = guidance
        sampling.update({key: found[key] for key in ("scheduler", "guidance", "negative") if key in found})
        steps = found.get("steps", steps)
        seed = found.get("seed", seed)
        width, height = found.get("width", width), found.get("height", height)
        # image-to-image, for Krea 2 and its checkpoints: the source picture and how much it shapes the result
        if body.options.get("image"):
            if slot["runner"] != "krea-2":
                raise HTTPException(400, "Image-to-image works with Krea 2 and its checkpoints")
            source = _source_image(body.options["image"], STAGING)
            strength = float(found.get("imageStrength", body.options.get("imageStrength", IMAGE_STRENGTH)))
            sampling["image"] = (str(source), max(0.0, min(1.0, strength)))
            if (not body.size or body.size == "source") and "width" not in found:
                from PIL import Image

                with Image.open(source) as picture:
                    width, height = _fit(*picture.size)
            notes.append(f"started from the image at influence {sampling['image'][1]:g}")
            if "imageStrength" in found:
                notes.append("Denoising strength read as the image's influence (1 minus it)")
    elif "<lora:" in body.prompt.lower():
        raise HTTPException(400, f"{slot.get('label', name)} takes no LoRAs; Krea 2, FLUX.2 [klein] 4B and their checkpoints do")

    if slot["runner"] in ("krea-2", "mflux-klein"):
        # the model needs the memory more than the preview's cached frames do
        from .render_api import release_frames

        release_frames()
    if body.options.get("continuous") and slot["runner"] == "krea-2":
        return _continuous(body, slot, name, prompt, stack, sampling, width, height, steps, notes)

    def operation(job_id, report, cancelled):
        STAGING.mkdir(parents=True, exist_ok=True)
        made = []
        timings = []
        extras: dict = {}  # what a model's licence sends with its pictures (Krea 2: its notice, the filter's warning)
        batch: list | None = None  # Krea 2: every seed in one run of mflux, the model loaded once
        seeds_used: list[int] = []
        for index in range(count):
            staged = STAGING / f"{uuid.uuid4().hex}{extension}"

            def each(f, message=None, i=index, **fields):
                label = message if count == 1 or message is None else f"Picture {i + 1} of {count}: {message}"
                report((i + f) / count, label, **fields)

            this_seed = (int(seed) + index) if seed is not None else None
            memory = str(body.options.get("memory") or "auto")
            checkpoint = Path(slot["checkpoint"]) if slot.get("checkpoint") else None
            if slot["runner"] == "krea-2":
                from .krea2 import generate_many

                if batch is None:
                    paths = [staged] + [STAGING / f"{uuid.uuid4().hex}{extension}" for _ in range(count - 1)]
                    seeds = [(int(seed) + i) if seed is not None else None for i in range(count)]
                    batch = generate_many(
                        prompt,
                        paths,
                        seeds,
                        width,
                        height,
                        steps=steps,
                        stack=stack,
                        memory=memory,
                        report=report,
                        cancelled=cancelled,
                        folder=checkpoint,
                        sampling=sampling,
                    )
                result = batch[index]
                if result.get("withheld"):
                    notes.append(
                        f"picture {index + 1} (seed {result['seed']}) withheld by the content filter, NSFW score {result['nsfw']:.2f}"
                    )
                    continue
                staged = Path(result["path"])
            elif slot["runner"] == "mflux-klein":
                from .klein import generate_to_file as klein_generate

                result = klein_generate(
                    slot.get("base", name),
                    prompt,
                    staged,
                    width=width,
                    height=height,
                    seed=this_seed,
                    steps=steps,
                    stack=stack,
                    memory=memory,
                    report=each,
                    cancelled=cancelled,
                    folder=checkpoint,
                )
            elif slot["runner"] == "command":
                result = run_command_slot(slot, body.prompt, staged, width, height, seconds, this_seed, each, cancelled)
            else:
                result = generate_to_file(
                    str(slot.get("folder") or name),
                    body.prompt,
                    staged,
                    negative=body.negative,
                    steps=steps,
                    guidance=guidance,
                    width=width,
                    height=height,
                    seed=this_seed,
                    report=each,
                    cancelled=cancelled,
                )
            timings.append(result["seconds"])
            extras.update({key: result[key] for key in ("notice", "warning") if result.get(key)})
            recipe = {}
            if slot["runner"] in ("krea-2", "mflux-klein") and result.get("seed") is not None:
                # what made the picture, written into the file as Automatic1111 writes it ("parameters"), so it can be
                # pasted back into the generator, and kept in the library's record
                recipe = _recipe(prompt, result, steps, stack, sampling, slot)
                _stamp(staged, recipe["parameters"])
                seeds_used.append(result["seed"])
            try:
                made.append(
                    ingest_path(
                        staged,
                        f"{body.prompt[:48]} ({name}, local)",
                        extra={
                            "source": "generated",
                            "generator": body.generator,
                            "prompt": body.prompt,
                            "seconds": result["seconds"],
                            "provider": result["provider"],
                            **{key: result[key] for key in ("notice", "contentFilter") if result.get(key) is not None},
                            **recipe,
                        },
                    )
                )
            finally:
                staged.unlink(missing_ok=True)
        if sampling.get("image"):
            Path(sampling["image"][0]).unlink(missing_ok=True)  # the source's staged copy
        return {
            "media": made,
            "kind": kind,
            "seconds": timings,
            "model": slot.get("id", name),
            "notes": notes,
            "seeds": seeds_used,
            **extras,
        }

    return jobs.submit("generate", operation)
