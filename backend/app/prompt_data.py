"""Prompts written the way Civitai shows them, as Automatic1111 and ComfyUI write them.

    a portrait, soft light <lora:Emotions V1:1.0> <lora:krea2_nose_slider_v1:-2.0>
    Negative prompt: blurry
    Steps: 9, CFG scale: 1, Sampler: Euler a beta, Seed: 1554, Model: silly_krea2, width: 840, height: 1256, ...

parse() takes that text apart: the prompt without its tags; each <lora:name:strength> (or <lyco:...>; a missing
strength is 1.0; A1111's second strength, for the text encoder, is ignored, as mflux has one); the negative prompt;
and the parameters line, its keys read without regard to case (Steps, CFG scale, Seed, Model, Size WxH or width and
height, Sampler, Clip skip). What formcut does with each is decided by the generator (generate.py), which reports what
it used and what it could not.

match_lora() finds a tag's LoRA in the library as A1111 does, by file name: exactly, then without regard to case,
then with spaces, dashes and underscores set aside; then by the name formcut keeps for it, and the file name it came
with from Civitai or Hugging Face.
"""

from __future__ import annotations

import re

_TAG = re.compile(r"<(?:lora|lyco):([^:<>]+?)(?::(-?\d+(?:\.\d+)?|-?\.\d+))?(?::[^<>]*)?>", re.IGNORECASE)
_PARAMS = re.compile(r"^\s*Steps:\s*\d+", re.IGNORECASE)
_NEGATIVE = re.compile(r"^\s*Negative prompt:\s*", re.IGNORECASE)


def _pairs(line: str) -> dict:
    """ "Key: value, Key: "quoted, value", ..." as a dict with lower-case keys."""
    out, key, value, quoted = {}, "", "", False
    buffer = ""
    for char in line + ",":
        if char == '"':
            quoted = not quoted
            buffer += char
        elif char == "," and not quoted:
            if ":" in buffer:
                key, value = buffer.split(":", 1)
                out[key.strip().lower()] = value.strip().strip('"')
            buffer = ""
        else:
            buffer += char
    return out


def parse(text: str) -> dict:
    lines = text.replace("\r\n", "\n").split("\n")
    params: dict = {}
    negative = ""
    prompt_lines = []
    in_negative = False
    for line in lines:
        if _PARAMS.match(line):
            params = _pairs(line)
            in_negative = False
        elif _NEGATIVE.match(line):
            negative = _NEGATIVE.sub("", line)
            in_negative = True
        elif in_negative:
            negative += "\n" + line
        else:
            prompt_lines.append(line)
    prompt = "\n".join(prompt_lines)
    loras = [(name.strip(), float(weight) if weight else 1.0) for name, weight in _TAG.findall(prompt)]
    prompt = re.sub(r"[ \t]{2,}", " ", _TAG.sub("", prompt)).strip()
    prompt = re.sub(r"\s*,\s*,+", ",", prompt).strip(" ,\n")
    return {"prompt": prompt, "negative": negative.strip(), "loras": loras, "params": _read(params)}


def _number(value, kind=float):
    try:
        return kind(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _read(raw: dict) -> dict:
    out = {}
    if "steps" in raw:
        out["steps"] = _number(raw["steps"], int)
    if "cfg scale" in raw:
        out["cfg"] = _number(raw["cfg scale"])
    if "seed" in raw:
        out["seed"] = _number(raw["seed"], int)
    if raw.get("model"):
        out["model"] = raw["model"]
    size = raw.get("size", "")
    if "x" in size:
        width, _, height = size.lower().partition("x")
        out["width"], out["height"] = _number(width, int), _number(height, int)
    if "width" in raw:
        out["width"] = _number(raw["width"], int)
    if "height" in raw:
        out["height"] = _number(raw["height"], int)
    if "denoising strength" in raw:
        out["denoising_strength"] = _number(raw["denoising strength"])
    for key in ("sampler", "schedule type", "clip skip", "version", "model hash"):
        if raw.get(key):
            out[key.replace(" ", "_")] = raw[key]
    return {k: v for k, v in out.items() if v is not None}


def _plain(text: str) -> str:
    return re.sub(r"[\s_\-.]+", "", text).lower()


def match_lora(name: str, entries: list[dict]) -> dict | None:
    """The library entry a <lora:name> tag means, or None."""
    stem = lambda entry: entry["file"].rsplit(".", 1)[0]  # noqa: E731
    for test in (
        lambda e: stem(e) == name,
        lambda e: stem(e).lower() == name.lower(),
        lambda e: _plain(stem(e)) == _plain(name),
        lambda e: _plain(e.get("name") or "") == _plain(name),
        lambda e: _plain((e.get("originalFile") or "").rsplit(".", 1)[0]) == _plain(name),
    ):
        found = [entry for entry in entries if entry.get("usable", True) and test(entry)]
        if found:
            return found[0]
    return None
