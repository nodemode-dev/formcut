"""transcribe: a media file to a transcript (JSON) and captions (SRT), through the engine's own transcriber.

The same path as POST /api/transcribe without the job queue: the model named by transcribe.model_for, fetched by the
model manager's pinned hub fetcher (one revision, every file checked against its SHA-256), the audio decoded by
transcribe.decode_audio, transcribed by transcribe.transcribe, and the captions cut by transcribe.phrases, the chunks the
interface lays out as caption clips, written by subtitles.write.
"""

from __future__ import annotations

import json

import httpx

from .. import subtitles
from .. import transcribe as engine
from .contract import FunctionError, checked_params, input_file, output_dir

LONGEST = 4 * 3600  # seconds; the engine's own transcription request takes no more


def transcribe_here(inputs: dict, params: dict, out_dir: str) -> dict:
    """The transcription in this process; the entry runs it isolated (isolation.py)."""
    options = checked_params("transcribe", params)
    media = input_file(inputs, "media")
    folder = output_dir(out_dir)
    if not engine.available():
        raise FunctionError("this engine has no ONNX Runtime; install backend/requirements.txt")
    language = options["language"]
    name = engine.model_for("en" if language == "en" else "auto", options["model"])
    try:
        audio = engine.decode_audio(media, 0.0, LONGEST, None)
    except ValueError as exc:
        raise FunctionError(f"no audio could be read from {media.name}: {_last_line(str(exc))}") from exc
    duration = len(audio) / engine.SAMPLE_RATE
    if duration >= LONGEST:
        raise FunctionError("the media is longer than 4 hours, the most one transcription takes")
    try:
        model = engine.load(name)
    except (ValueError, OSError, httpx.HTTPError) as exc:
        raise FunctionError(f"the Whisper model {name} could not be fetched: {exc}") from exc
    segments = engine.transcribe(model, audio, language) if len(audio) >= engine.SAMPLE_RATE // 10 else []
    transcript = {
        "model": name,
        "size": options["model"],
        "language": language,
        "provider": model.provider,
        "duration": round(duration, 3),
        "segments": segments,
    }
    chunks, _ = engine.phrases(segments, None)
    cues = [subtitles.Cue(start=c["start"], end=c["end"], text=c["text"]) for c in chunks if c["text"].strip()]
    transcript_path = folder / "transcript.json"
    subtitles_path = folder / "subtitles.srt"
    transcript_path.write_text(json.dumps(transcript, ensure_ascii=False, indent=1), encoding="utf-8")
    subtitles_path.write_text(subtitles.write(cues, "srt") if cues else "", encoding="utf-8")
    return {"transcript": str(transcript_path), "subtitles": str(subtitles_path)}


def _last_line(text: str) -> str:
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[-1] if lines else "ffmpeg could not decode it"
