import itertools
import json
import math
import statistics
import subprocess
import threading
from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import jobs
from .media import MEDIA_DIR, _find
from .model_manager import HUB, hub_fetch, providers
from .processes import communicate

router = APIRouter(prefix="/api/transcribe", tags=["transcribe"])

# The same Hugging Face exports the browser worker loads through the hub route,
# now run in the engine's own ONNX Runtime with the shared provider ordering, so
# the model is no longer capped at small by what the webview can hold and the
# interface thread stays free. Medium and large exist only here.
ENGLISH = {
    "tiny": "Xenova/whisper-tiny.en",
    "base": "Xenova/whisper-base.en",
    "small": "Xenova/whisper-small.en",
    "medium": "Xenova/whisper-medium.en",
    "large": "onnx-community/whisper-large-v3-turbo",
}
MULTILINGUAL = {
    "tiny": "onnx-community/whisper-tiny",
    "base": "onnx-community/whisper-base",
    "small": "onnx-community/whisper-small",
    "medium": "Xenova/whisper-medium",
    "large": "onnx-community/whisper-large-v3-turbo",
}
FILES = (
    "config.json",
    "generation_config.json",
    "tokenizer.json",
    "onnx/encoder_model_quantized.onnx",
    "onnx/decoder_model_merged_quantized.onnx",
)
SAMPLE_RATE = 16000
N_FFT = 400
HOP = 160
WINDOW_SAMPLES = 30 * SAMPLE_RATE
FRAMES = WINDOW_SAMPLES // HOP
FRAME_SECONDS = HOP / SAMPLE_RATE
_lock = threading.Lock()
_loaded: dict = {}


def model_for(language: str, size: str) -> str:
    table = ENGLISH if language == "en" else MULTILINGUAL
    return table.get(size, table["tiny"])


def mel_filters(n_mels: int) -> np.ndarray:
    """The slaney mel filterbank Whisper was trained with, computed rather than shipped."""

    def to_mel(f):
        f = np.asarray(f, np.float64)
        return np.where(f >= 1000.0, 15.0 + np.log(np.maximum(f, 1e-9) / 1000.0) / (math.log(6.4) / 27.0), f / 200.0 * 3)

    def to_hz(m):
        m = np.asarray(m, np.float64)
        return np.where(m >= 15.0, 1000.0 * np.exp((math.log(6.4) / 27.0) * (m - 15.0)), 200.0 * m / 3)

    fft_freqs = np.linspace(0, SAMPLE_RATE / 2, 1 + N_FFT // 2)
    points = to_hz(np.linspace(to_mel(0.0), to_mel(SAMPLE_RATE / 2), n_mels + 2))
    diff = np.diff(points)
    ramps = points[:, None] - fft_freqs[None, :]
    weights = np.maximum(0, np.minimum(-ramps[:-2] / diff[:-1, None], ramps[2:] / diff[1:, None]))
    weights *= (2.0 / (points[2 : n_mels + 2] - points[:n_mels]))[:, None]
    return weights.astype(np.float32)


_window = np.hanning(N_FFT + 1)[:-1].astype(np.float32)


def log_mel(audio: np.ndarray, filters: np.ndarray) -> np.ndarray:
    """One padded 30 s window as Whisper's log-mel spectrogram, (n_mels, 3000)."""
    padded = np.zeros(WINDOW_SAMPLES, np.float32)
    padded[: min(len(audio), WINDOW_SAMPLES)] = audio[:WINDOW_SAMPLES]
    padded = np.pad(padded, N_FFT // 2, mode="reflect")
    frames = np.lib.stride_tricks.sliding_window_view(padded, N_FFT)[::HOP]
    spectrum = np.fft.rfft(frames * _window, axis=1)
    magnitudes = (spectrum.real**2 + spectrum.imag**2)[:-1].T.astype(np.float32)
    log_spec = np.log10(np.maximum(filters @ magnitudes, 1e-10))
    log_spec = np.maximum(log_spec, log_spec.max() - 8.0)
    return ((log_spec + 4.0) / 4.0).astype(np.float32)


class Tokenizer:
    """The decoding half of Whisper's byte-level BPE, read from tokenizer.json."""

    def __init__(self, path: Path):
        data = json.loads(path.read_text(encoding="utf-8"))
        self.id_to_token = {v: k for k, v in data["model"]["vocab"].items()}
        self.special = {}
        for entry in data.get("added_tokens", []):
            self.id_to_token[entry["id"]] = entry["content"]
            self.special[entry["content"]] = entry["id"]
        printable = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
        mapped = list(printable)
        extra = 0
        for byte in range(256):
            if byte not in printable:
                printable.append(byte)
                mapped.append(256 + extra)
                extra += 1
        self.byte_of = {chr(m): b for b, m in zip(printable, mapped, strict=True)}
        self.eot = self.special["<|endoftext|>"]
        self.sot = self.special["<|startoftranscript|>"]
        self.no_timestamps = self.special["<|notimestamps|>"]
        self.timestamp_begin = self.no_timestamps + 1
        self.no_speech = self.special.get("<|nospeech|>", self.special.get("<|nocaptions|>"))
        self.transcribe = self.special.get("<|transcribe|>")
        self.languages = {k[2:-2]: v for k, v in self.special.items() if len(k) <= 7 and k[2:-2].isalpha() and k[2:-2].islower()}

    def text_of(self, ids) -> str:
        pieces = "".join(self.id_to_token.get(int(i), "") for i in ids if int(i) < self.eot)
        return bytes(self.byte_of.get(ch, 63) for ch in pieces).decode("utf-8", errors="replace")


def median_filter(matrix: np.ndarray, width: int = 7) -> np.ndarray:
    pad = width // 2
    padded = np.pad(matrix, ((0, 0), (pad, pad)), mode="reflect")
    return np.median(np.lib.stride_tricks.sliding_window_view(padded, width, axis=1), axis=2)


def dtw(cost: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Monotonic alignment of tokens (rows) to audio frames (columns) of least summed cost."""
    n, m = cost.shape
    acc = np.full((n + 1, m + 1), np.inf, np.float64)
    trace = np.zeros((n + 1, m + 1), np.int8)
    acc[0, 0] = 0
    for i in range(1, n + 1):
        row, above, best = cost[i - 1], acc[i - 1], acc[i]
        for j in range(1, m + 1):
            c0, c1, c2 = above[j - 1], above[j], best[j - 1]
            if c0 <= c1 and c0 <= c2:
                best[j], trace[i, j] = c0 + row[j - 1], 0
            elif c1 <= c2:
                best[j], trace[i, j] = c1 + row[j - 1], 1
            else:
                best[j], trace[i, j] = c2 + row[j - 1], 2
    i, j = n, m
    xs, ys = [], []
    while i > 0 or j > 0:
        xs.append(i - 1)
        ys.append(j - 1)
        step = trace[i, j]
        if step == 0:
            i, j = i - 1, j - 1
        elif step == 1:
            i -= 1
        else:
            j -= 1
    return np.array(xs[::-1]), np.array(ys[::-1])


class Whisper:
    """One model's two sessions, its tokenizer and the decoding rules."""

    def __init__(self, folder: Path, execution_providers: list[str]):
        import onnxruntime as ort

        self.config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
        self.generation = json.loads((folder / "generation_config.json").read_text(encoding="utf-8"))
        self.tokens = Tokenizer(folder / "tokenizer.json")
        options = ort.SessionOptions()
        options.log_severity_level = 3
        self.encoder = ort.InferenceSession(str(folder / "onnx/encoder_model_quantized.onnx"), options, providers=execution_providers)
        self.decoder = ort.InferenceSession(
            str(folder / "onnx/decoder_model_merged_quantized.onnx"), options, providers=execution_providers
        )
        self.provider = self.decoder.get_providers()[0]
        self.layers = int(self.config["decoder_layers"])
        self.heads = int(self.config["decoder_attention_heads"])
        self.head_dim = int(self.config["d_model"]) // self.heads
        self.filters = mel_filters(int(self.config["num_mel_bins"]))
        self.multilingual = bool(self.generation.get("is_multilingual") or self.generation.get("lang_to_id"))
        available = {o.name for o in self.decoder.get_outputs()}
        heads = self.generation.get("alignment_heads") or []
        # large-v3-turbo ships large-v3's alignment heads, which name decoder
        # layers the four-layer turbo does not have; then, as Whisper did before
        # alignment heads existed, every head of the second half of the layers.
        if not heads or any(layer >= self.layers for layer, _ in heads):
            heads = [[layer, head] for layer in range(self.layers // 2, self.layers) for head in range(self.heads)]
        self.alignment = heads
        self.cross_names = [
            f"cross_attentions.{layer}" for layer in sorted({layer for layer, _ in heads}) if f"cross_attentions.{layer}" in available
        ]
        present = {f"present.{n}.{side}.{kind}" for n in range(self.layers) for side in ("decoder", "encoder") for kind in ("key", "value")}
        self.outputs = ["logits", *sorted(present & available), *self.cross_names]
        self.suppress = [int(t) for t in self.generation.get("suppress_tokens", [])]
        self.begin_suppress = [int(t) for t in self.generation.get("begin_suppress_tokens", [])]

    def encode(self, mel: np.ndarray) -> np.ndarray:
        return self.encoder.run(["last_hidden_state"], {"input_features": mel[None]})[0]

    def language_of(self, hidden: np.ndarray) -> int:
        logits, _ = self._step(np.array([[self.tokens.sot]], np.int64), hidden, None)
        ids = np.array(sorted(self.tokens.languages.values()))
        return int(ids[np.argmax(logits[-1][ids])])

    def _step(self, tokens: np.ndarray, hidden: np.ndarray, past):
        feeds = {"input_ids": tokens, "encoder_hidden_states": hidden}
        if past is None:
            empty = np.zeros((1, self.heads, 0, self.head_dim), np.float32)
            for n in range(self.layers):
                for side in ("decoder", "encoder"):
                    feeds[f"past_key_values.{n}.{side}.key"] = empty
                    feeds[f"past_key_values.{n}.{side}.value"] = empty
            feeds["use_cache_branch"] = np.array([False])
        else:
            feeds.update(past)
            feeds["use_cache_branch"] = np.array([True])
        out = dict(zip(self.outputs, self.decoder.run(self.outputs, feeds), strict=True))
        new_past = {}
        for n in range(self.layers):
            for kind in ("key", "value"):
                new_past[f"past_key_values.{n}.decoder.{kind}"] = out[f"present.{n}.decoder.{kind}"]
                key = f"past_key_values.{n}.encoder.{kind}"
                new_past[key] = out[f"present.{n}.encoder.{kind}"] if past is None else past[key]
        cross = np.concatenate([out[name][0] for name in self.cross_names], axis=0) if self.cross_names else None
        return out["logits"][0], (new_past, cross)

    def decode_window(self, hidden: np.ndarray, prompt: list[int], max_tokens: int = 224, cancelled=lambda: False):
        """Greedy decoding under Whisper's timestamp rules; the alignment heads' attention rides along."""
        tb, eot = self.tokens.timestamp_begin, self.tokens.eot
        tokens = list(prompt)
        attention = []
        past = None
        current = np.array([tokens], np.int64)
        no_speech = None
        for _ in range(max_tokens):
            if cancelled():
                raise InterruptedError("Cancelled")
            logits, (past, cross) = self._step(current, hidden, past)
            if cross is not None:
                attention.append(cross)
            row = logits[-1].astype(np.float64)
            if no_speech is None and self.tokens.no_speech is not None:
                probs = np.exp(row - row.max())
                no_speech = float(probs[self.tokens.no_speech] / probs.sum())
            row[self.suppress] = -np.inf
            row[self.tokens.no_timestamps] = -np.inf
            seq = tokens[len(prompt) :]
            if not seq:
                row[self.begin_suppress] = -np.inf
                row[:tb] = -np.inf
                row[tb + int(self.generation.get("max_initial_timestamp_index", 50)) + 1 :] = -np.inf
            else:
                last_stamp = seq[-1] >= tb
                penultimate_stamp = len(seq) < 2 or seq[-2] >= tb
                if last_stamp:
                    if penultimate_stamp:
                        row[tb:] = -np.inf
                    else:
                        row[:eot] = -np.inf
                stamps = [t for t in seq if t >= tb]
                if stamps:
                    row[tb : stamps[-1] if last_stamp and not penultimate_stamp else stamps[-1] + 1] = -np.inf
            shift = row.max()
            logprobs = row - (shift + np.log(np.exp(row - shift).sum()))
            stamp_mass = np.log(np.exp(logprobs[tb:]).sum()) if np.isfinite(logprobs[tb:]).any() else -np.inf
            if stamp_mass > logprobs[:tb].max():
                row[:tb] = -np.inf
            choice = int(np.argmax(row))
            tokens.append(choice)
            if choice == eot:
                break
            current = np.array([[choice]], np.int64)
        return tokens[len(prompt) :], (np.concatenate(attention, axis=1) if attention else None), no_speech


def _word_spans(
    model: Whisper, text_tokens: list[int], attention: np.ndarray, prompt_len: int, audio_frames: int
) -> list[tuple[int, int, float, float]]:
    """(first token, last token, start, end) per word from DTW over the alignment heads, seconds within the window."""
    if attention is None or not text_tokens:
        return []
    layer_index = {int(name.split(".")[1]): i for i, name in enumerate(model.cross_names)}
    picked = [attention[layer_index[layer] * model.heads + head] for layer, head in model.alignment if layer in layer_index]
    weights = np.stack(picked)[:, prompt_len : prompt_len + len(text_tokens), : max(2, audio_frames // 2)]
    weights = (weights - weights.mean(axis=-2, keepdims=True)) / np.maximum(weights.std(axis=-2, keepdims=True), 1e-9)
    matrix = np.stack([median_filter(w) for w in weights]).mean(axis=0)
    text_indices, time_indices = dtw(-matrix)
    jumps = np.pad(np.diff(text_indices), (1, 0), constant_values=1).astype(bool)
    jump_times = time_indices[jumps] * FRAME_SECONDS * 2
    window_end = matrix.shape[1] * FRAME_SECONDS * 2
    bounds = []
    start = None
    for i, token in enumerate(text_tokens):
        if i == 0 or model.tokens.id_to_token.get(token, "").startswith("Ġ"):
            if start is not None:
                bounds.append((start, i))
            start = i
    bounds.append((start or 0, len(text_tokens)))
    out = []
    for a, b in bounds:
        t0 = float(jump_times[min(a, len(jump_times) - 1)])
        t1 = float(jump_times[b]) if b < len(jump_times) else window_end
        out.append((a, b, t0, max(t0, t1)))
    return out


def _tidy(words: list[dict]) -> list[dict]:
    """Whisper's own clean-up: a word never shorter than 50 ms, and a word that the alignment dragged out (twice the median, which happens at sentence ends over silence) cut back."""
    if not words:
        return words
    durations = [max(0.0, w["end"] - w["start"]) for w in words]
    ceiling = max(0.6, 2 * statistics.median(durations))
    for word, duration in zip(words, durations, strict=True):
        if duration > ceiling:
            word["end"] = word["start"] + ceiling
        if word["end"] - word["start"] < 0.05:
            word["end"] = word["start"] + 0.05
    for earlier, later in itertools.pairwise(words):
        if later["start"] > earlier["start"]:
            earlier["end"] = min(earlier["end"], later["start"])
    return words


def _repetitive(text: str) -> bool:
    """The worker's hallucination filter: tiny models loop phrases on silence."""
    words = [w for w in text.lower().split() if w]
    if len(words) < 4:
        return False
    for length in (2, 3, 4):
        seen: dict = {}
        for i in range(len(words) - length + 1):
            phrase = " ".join(words[i : i + length])
            seen[phrase] = seen.get(phrase, 0) + 1
            if seen[phrase] > 3:
                return True
    counts: dict = {}
    for word in words:
        counts[word] = counts.get(word, 0) + 1
        if counts[word] > len(words) * 0.5 and counts[word] > 4:
            return True
    return False


def transcribe(
    model: Whisper, audio: np.ndarray, language: str = "en", report=lambda fraction: None, cancelled=lambda: False
) -> list[dict]:
    """Segments with word times over the whole audio, one 30 s window at a time, seeking by the last complete timestamp pair."""
    tb = model.tokens.timestamp_begin
    total = len(audio)
    whole = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))) if total else 0.0
    seek = 0
    segments: list[dict] = []
    lang = None
    while seek < total:
        chunk = audio[seek : seek + WINDOW_SAMPLES]
        hidden = model.encode(log_mel(chunk, model.filters))
        audio_frames = min(FRAMES, math.ceil(len(chunk) / HOP))
        if model.multilingual:
            if lang is None:
                lang = model.tokens.languages.get(language) if language not in ("", "auto") else model.language_of(hidden)
                lang = lang if lang is not None else model.language_of(hidden)
            prompt = [model.tokens.sot, lang, model.tokens.transcribe]
        else:
            prompt = [model.tokens.sot]
        tokens, attention, no_speech = model.decode_window(hidden, prompt, cancelled=cancelled)
        text_tokens = [t for t in tokens if t < model.tokens.eot]
        offset = seek / SAMPLE_RATE
        if (no_speech is not None and no_speech > 0.6) or not text_tokens:
            seek += WINDOW_SAMPLES
            report(min(0.99, seek / total))
            continue
        spans = _word_spans(model, text_tokens, attention, len(prompt), audio_frames)
        stamps = [(i, t) for i, t in enumerate(tokens) if t >= tb]
        pairs = []
        text_pos = 0
        for k in range(0, len(stamps) - 1, 2):
            (i0, t0), (i1, t1) = stamps[k], stamps[k + 1]
            inner = [t for t in tokens[i0 + 1 : i1] if t < model.tokens.eot]
            pairs.append(((t0 - tb) * 0.02, (t1 - tb) * 0.02, text_pos, text_pos + len(inner), inner))
            text_pos += len(inner)
        if not pairs:
            pairs.append((0.0, len(chunk) / SAMPLE_RATE, 0, len(text_tokens), text_tokens))
        for start, stamped_end, a, b, inner in pairs:
            text = model.tokens.text_of(inner).strip()
            end = min(stamped_end, len(chunk) / SAMPLE_RATE)
            if not text or end <= start or _repetitive(text):
                continue
            region = audio[seek + int(start * SAMPLE_RATE) : seek + int(end * SAMPLE_RATE)]
            # A segment "heard" over silence is the model filling the quiet
            # with a stock phrase; the audio under it says whether anyone spoke.
            level = float(np.sqrt(np.mean(region.astype(np.float64) ** 2))) if len(region) else 0.0
            if whole and level < 0.15 * whole:
                continue
            words = []
            for wa, wb, w0, w1 in spans:
                if wa >= a and wb <= b:
                    word = model.tokens.text_of(text_tokens[wa:wb]).strip()
                    if word:
                        words.append({"text": word, "start": w0, "end": w1})
            for word in _tidy(words):
                word["start"] = round(offset + word["start"], 3)
                word["end"] = round(offset + word["end"], 3)
            segments.append({"text": text, "start": round(offset + start, 3), "end": round(offset + end, 3), "words": words})
        consumed = None
        if len(stamps) >= 2 and len(stamps) % 2 == 0 and stamps[-1][0] == len(tokens) - 2 and tokens[-1] == model.tokens.eot:
            consumed = (stamps[-1][1] - tb) * 0.02
        seek += int(consumed * SAMPLE_RATE) if consumed and consumed > 0 else WINDOW_SAMPLES
        report(min(0.99, seek / total))
    return segments


def phrases(segments: list[dict], words_per_caption: int | None) -> tuple[list[dict], bool]:
    """The worker's phrasesFromWords, so the interface receives the same chunk shape either way."""
    cap = words_per_caption if words_per_caption and words_per_caption > 0 else 6
    words = [w for s in segments for w in s["words"]]
    if not words or any(not s["words"] for s in segments):
        return [{"text": s["text"], "start": s["start"], "end": s["end"]} for s in segments], False
    out: list[dict] = []
    phrase = None
    for word in words:
        start, end, text = word["start"], max(word["end"], word["start"] + 0.05), word["text"]
        held = phrase["words"] if phrase is not None else []
        closes = (
            phrase is None
            or len(held) >= cap
            or start - phrase["end"] > 0.7
            or end - phrase["start"] > 3.5
            or held[-1]["text"][-1:] in ".!?"
        )
        if closes:
            phrase = {"text": "", "start": start, "end": end, "words": []}
            out.append(phrase)
        phrase["words"].append({"t": round(start - phrase["start"], 3), "d": round(max(0.05, end - start), 3), "text": text})
        phrase["end"] = max(phrase["end"], end)
        phrase["text"] = " ".join(w["text"] for w in phrase["words"])
    return out, True


def load(name: str, report=lambda fraction: None, cancelled=lambda: False) -> Whisper:
    """The model's sessions, fetched through the hub on first use and kept for the next call."""
    with _lock:
        if name in _loaded:
            return _loaded[name]
    for n, path in enumerate(FILES):
        if cancelled():
            raise InterruptedError("Cancelled")
        if hub_fetch(name, path) is None:
            raise ValueError(f"The model file {name}/{path} is not available")
        report(0.05 * (n + 1) / len(FILES))
    model = Whisper(HUB.joinpath(*name.split("/")), providers())
    with _lock:
        _loaded.clear()
        _loaded[name] = model
    return model


def decode_audio(path: Path, start: float, duration: float, stream: int | None, cancelled=lambda: False) -> np.ndarray:
    command = ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, start):.3f}", "-t", f"{max(0.0, duration):.3f}", "-i", str(path)]
    if stream is not None:
        command += ["-map", f"0:a:{int(stream)}"]
    command += ["-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = communicate(process, cancelled=cancelled)
    if process.returncode:
        raise ValueError(error.decode(errors="replace")[-1000:] or "Could not decode the audio")
    return np.frombuffer(output, "<f4").copy()


def cached(name: str) -> bool:
    return all(HUB.joinpath(*name.split("/"), *path.split("/")).is_file() for path in FILES)


class TranscribeInput(BaseModel):
    mediaId: str
    sourceIn: float = Field(0.0, ge=0)
    duration: float = Field(..., gt=0, le=4 * 3600)
    language: str = "en"
    size: str = "tiny"
    wordsPerCaption: int | None = Field(None, ge=1, le=20)
    audioStream: int | None = Field(None, ge=0)


def available() -> bool:
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


@router.get("/status")
def status() -> dict:
    return {
        "available": available(),
        "providers": providers() if available() else [],
        "sizes": list(ENGLISH),
        "cached": {name: cached(name) for name in {*ENGLISH.values(), *MULTILINGUAL.values()}},
    }


@router.post("", status_code=202)
def start(body: TranscribeInput) -> dict:
    if not available():
        raise HTTPException(503, "The engine has no ONNX Runtime; the interface transcribes in the browser instead")
    _find(body.mediaId)
    paths = list(MEDIA_DIR.glob(f"{body.mediaId}.*"))
    if not paths:
        raise HTTPException(404, "Media file is missing")
    name = model_for("en" if body.language == "en" else "auto", body.size)

    def run(_id, report, cancelled):
        model = load(name, report, cancelled)
        audio = decode_audio(paths[0], body.sourceIn, body.duration, body.audioStream, cancelled)
        if len(audio) < SAMPLE_RATE // 10:
            return {"chunks": [], "byWord": False, "model": name, "provider": model.provider}
        segments = transcribe(model, audio, body.language, lambda f: report(0.05 + 0.95 * f), cancelled)
        chunks, by_word = phrases(segments, body.wordsPerCaption)
        return {"chunks": chunks, "byWord": by_word, "model": name, "provider": model.provider}

    return jobs.submit("transcribe", run)
