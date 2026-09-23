import json
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import jobs
from .media import ingest_path
from .model_manager import ROOT, ready
from .paths import DATA_DIR
from .processes import communicate

router = APIRouter(prefix="/api/speech", tags=["speech"])

# The local speech engines. Kokoro's model files come through the model manager;
# Pocket TTS and Chatterbox are Python packages installed into the speech
# runtime on request (both bring PyTorch, which the frozen engine never carries),
# and fetch their weights from Hugging Face into formcut's data directory.
ENGINES = {
    "kokoro": {"name": "Kokoro", "module": "kokoro_onnx", "package": "kokoro-onnx==0.6.1", "license": "Apache-2.0"},
    "pocket": {"name": "Pocket TTS", "module": "pocket_tts", "package": "pocket-tts", "license": "MIT code, CC-BY-4.0 weights (Kyutai)"},
    "chatterbox": {
        "name": "Chatterbox",
        "module": "chatterbox",
        "package": "chatterbox-tts",
        "license": "MIT (Resemble AI); every output carries an inaudible watermark",
    },
}
# Pocket TTS's documented voices; the installed package names its full catalogue
# (26 in 3.1.0), which pocket_voices() reads when it can.
POCKET_VOICES = ["alba", "marius", "javert", "jean", "fantine", "cosette", "eponine", "azelma"]
POCKET_CATALOGUE = "from pocket_tts.default_parameters import _ORIGINS_OF_PREDEFINED_VOICES as v; import json; print(json.dumps(sorted(v)))"
CLONING_GATED = "could not download the weights for the model with voice cloning"
# The speech panel's language codes, as Chatterbox's multilingual model names them.
CHATTERBOX_LANGUAGES = {"en-us": "en", "en-gb": "en", "es": "es", "fr-fr": "fr", "it": "it", "pt-br": "pt", "ja": "ja", "cmn": "zh"}
REFERENCE_SECONDS = 20

# The PyTorch workers end with os._exit once the WAV is written and flushed:
# Pocket TTS 3.1.0 aborted during interpreter shutdown in five runs of six here
# ('terminate called without an active exception', a native thread never
# joined), after the audio was already complete, which failed the job.
POCKET_WORKER = """
import json,sys,wave
import numpy as np
from pocket_tts import TTSModel
args=json.load(sys.stdin)
model=TTSModel.load_model()
state=model.get_state_for_audio_prompt(args["reference"] or args["voice"])
audio=model.generate_audio(state,args["text"]).detach().cpu().numpy().reshape(-1)
with wave.open(args["output"],"wb") as out:
 out.setnchannels(1)
 out.setsampwidth(2)
 out.setframerate(int(model.sample_rate))
 out.writeframes(np.round(np.clip(audio,-1,1)*32767).astype("<i2").tobytes())
import os
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
"""

CHATTERBOX_WORKER = """
import json,sys,wave
import numpy as np
import torch
args=json.load(sys.stdin)
mps=getattr(torch.backends,"mps",None)
device="cuda" if torch.cuda.is_available() else ("mps" if mps is not None and mps.is_available() else "cpu")
options={"audio_prompt_path":args["reference"] or None,"exaggeration":args["exaggeration"],"cfg_weight":args["cfg"]}
if args["language"]=="en":
 from chatterbox.tts import ChatterboxTTS
 model=ChatterboxTTS.from_pretrained(device=device)
 wav=model.generate(args["text"],**options)
else:
 from chatterbox.mtl_tts import ChatterboxMultilingualTTS
 model=ChatterboxMultilingualTTS.from_pretrained(device=device)
 wav=model.generate(args["text"],language_id=args["language"],**options)
audio=wav.detach().cpu().numpy().reshape(-1)
with wave.open(args["output"],"wb") as out:
 out.setnchannels(1)
 out.setsampwidth(2)
 out.setframerate(int(model.sr))
 out.writeframes(np.round(np.clip(audio,-1,1)*32767).astype("<i2").tobytes())
import os
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
"""

WORKER = """
import json,sys,wave
import numpy as np
from kokoro_onnx import Kokoro
args=json.load(sys.stdin)
engine=Kokoro(args["model"],args["voices"])
audio,rate=engine.create(args["text"],voice=args["voice"],speed=args["speed"],lang=args["language"])
with wave.open(args["output"],"wb") as out:
 out.setnchannels(1)
 out.setsampwidth(2)
 out.setframerate(rate)
 out.writeframes(np.round(np.clip(audio,-1,1)*32767).astype("<i2").tobytes())
"""


_runtime: dict = {}


def interpreter():
    override = os.environ.get("FORMCUT_AI_PYTHON")
    venv = DATA_DIR / "ai-runtime" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    candidate = override or (str(venv) if venv.is_file() else (sys.executable if not getattr(sys, "frozen", False) else None))
    if not candidate:
        return None
    if _runtime.get(candidate):
        return candidate
    probe = subprocess.run([candidate, "-c", "import kokoro_onnx"], capture_output=True, text=True, check=False)
    if probe.returncode:
        return None
    _runtime[candidate] = True
    return candidate


def runtime() -> str | None:
    """The speech runtime's Python, whatever it has installed: the override, or data/ai-runtime."""
    override = os.environ.get("FORMCUT_AI_PYTHON")
    venv = DATA_DIR / "ai-runtime" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return override or (str(venv) if venv.is_file() else None)


def installed(engine: str) -> bool:
    python = interpreter() if engine == "kokoro" else runtime()
    if not python:
        return False
    key = f"{python}:{engine}"
    if _runtime.get(key) is None:
        probe = subprocess.run([python, "-c", f"import {ENGINES[engine]['module']}"], capture_output=True, text=True, check=False)
        _runtime[key] = probe.returncode == 0
    return bool(_runtime[key])


def _worker_env() -> dict:
    """The environment a speech worker runs in: its own libraries, formcut's model folder.

    Importing OpenCV adds its bundled library folder to LD_LIBRARY_PATH (and
    DYLD_LIBRARY_PATH on macOS), and every child process inherits it. The speech
    runtime is another Python with its own native libraries, so those entries
    are dropped rather than let it load the engine's. Model downloads land in
    formcut's data directory, where Storage can see and clear them.
    """
    env = dict(os.environ)
    for name in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        kept = [part for part in env.get(name, "").split(os.pathsep) if part and "cv2" not in Path(part).parts]
        if kept:
            env[name] = os.pathsep.join(kept)
        else:
            env.pop(name, None)
    cache = DATA_DIR / "models" / "huggingface"
    cache.mkdir(parents=True, exist_ok=True)
    return {**env, "HF_HOME": str(cache), "TORCH_HOME": str(DATA_DIR / "models" / "torch")}


def pocket_voices() -> list[str]:
    python = runtime()
    if not python or not installed("pocket"):
        return POCKET_VOICES
    key = f"{python}:pocket-voices"
    if key not in _runtime:
        probe = subprocess.run([python, "-c", POCKET_CATALOGUE], capture_output=True, text=True, check=False)
        try:
            listed = json.loads(probe.stdout) if probe.returncode == 0 else None
        except ValueError:
            listed = None
        _runtime[key] = listed if isinstance(listed, list) and listed else POCKET_VOICES
    return _runtime[key]


@router.get("/engines")
def engines():
    return [{"id": key, **spec, "installed": installed(key), "runtime": bool(runtime() or interpreter())} for key, spec in ENGINES.items()]


@router.post("/engines/{engine}/install", status_code=202)
def install(engine: str):
    if engine not in ("pocket", "chatterbox"):
        raise HTTPException(404, "No installable speech engine by that name")
    python = runtime()
    if not python:
        raise HTTPException(409, "Run setup_local_ai to create the speech runtime first")

    def operation(job_id, report, cancelled):
        steps = []
        if sys.platform.startswith("linux"):
            # On Linux the default PyTorch wheel carries CUDA (gigabytes); the CPU
            # build is enough for both engines and installs first so it is kept.
            steps.append([python, "-m", "pip", "install", "--index-url", "https://download.pytorch.org/whl/cpu", "torch"])
        steps.append([python, "-m", "pip", "install", ENGINES[engine]["package"]])
        for number, command in enumerate(steps):
            report(number / len(steps))
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                _stdout, stderr = communicate(process, "", timeout=3600, cancelled=cancelled)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
            if cancelled():
                raise InterruptedError("Cancelled")
            if process.returncode:
                last = next((line.strip() for line in reversed(stderr.strip().splitlines()) if line.strip()), "")
                raise ValueError(f"{ENGINES[engine]['name']} could not be installed. {last[:200]}")
        _runtime.pop(f"{python}:{engine}", None)
        return {"engine": engine, "installed": installed(engine)}

    return jobs.submit("speech-install", operation)


@router.get("/voices")
def voices(engine: str = "kokoro"):
    if engine == "pocket":
        return {
            "ready": True,
            "runtime": bool(runtime()),
            "installed": installed("pocket"),
            "voices": [{"id": v, "name": v.replace("_", " ").title()} for v in pocket_voices()],
        }
    if engine == "chatterbox":
        return {
            "ready": True,
            "runtime": bool(runtime()),
            "installed": installed("chatterbox"),
            "voices": [{"id": "default", "name": "Chatterbox"}],
        }
    if not ready("local-speech"):
        return {"ready": False, "runtime": bool(interpreter()), "voices": []}
    import numpy as np

    with np.load(ROOT / "voices-v1.0.bin", allow_pickle=False) as data:
        return {"ready": True, "runtime": bool(interpreter()), "voices": [{"id": key, "name": key.replace("_", " ")} for key in data.files]}


class SpeechInput(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    voice: str = "af_heart"
    language: str = "en-us"
    speed: float = Field(default=1, ge=0.5, le=2)
    engine: str = "kokoro"
    reference: str | None = None  # a media id whose voice to clone
    consent: bool = False  # the person confirms the speaker agreed
    exaggeration: float = Field(default=0.5, ge=0.25, le=2)
    cfg: float = Field(default=0.5, ge=0, le=1)


def _reference_clip(media_id: str, folder) -> str:
    """The first seconds of a clip's sound, as the mono WAV both cloning engines read."""
    from .media import MEDIA_DIR, _find

    _find(media_id)
    sources = list(MEDIA_DIR.glob(f"{media_id}.*"))
    if not sources:
        raise HTTPException(404, "The voice reference is not in the library")
    target = folder / f"reference-{media_id}.wav"
    command = [
        "ffmpeg",
        "-v",
        "error",
        "-y",
        "-i",
        str(sources[0]),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "24000",
        "-t",
        str(REFERENCE_SECONDS),
        str(target),
    ]
    if subprocess.run(command, capture_output=True, check=False).returncode or not target.is_file():
        raise HTTPException(422, "The voice reference has no sound formcut can read")
    return str(target)


def _speak_with(body: SpeechInput):
    """A job for Pocket TTS or Chatterbox."""
    python = runtime()
    if not python:
        raise HTTPException(409, "Run setup_local_ai to create the speech runtime first")
    if not installed(body.engine):
        raise HTTPException(409, f"Install {ENGINES[body.engine]['name']} first")
    if body.engine == "pocket" and not body.reference and body.voice not in pocket_voices():
        raise HTTPException(422, "Pocket TTS has no voice by that name")
    if body.reference and not body.consent:
        raise HTTPException(422, "Cloning a voice needs the speaker's permission")
    language = CHATTERBOX_LANGUAGES.get(body.language, "en")

    def operation(job_id, report, cancelled):
        folder = DATA_DIR / "speech"
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / (job_id + ".wav")
        reference = _reference_clip(body.reference, folder) if body.reference else None
        args = {**body.model_dump(), "language": language, "reference": reference, "output": str(output)}
        worker = POCKET_WORKER if body.engine == "pocket" else CHATTERBOX_WORKER
        process = subprocess.Popen(
            [python, "-c", worker], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_worker_env()
        )
        try:
            _stdout, stderr = communicate(process, json.dumps(args), timeout=1800, cancelled=cancelled)
            if cancelled():
                raise InterruptedError("Cancelled")
            if process.returncode:
                print(f"{body.engine} speech worker failed:\n" + stderr[-2000:], file=sys.stderr, flush=True)
                if CLONING_GATED in stderr:
                    raise ValueError(
                        "Pocket TTS clones voices with Kyutai's gated weights: accept their terms at "
                        "huggingface.co/kyutai/pocket-tts and give formcut a Hugging Face token (HF_TOKEN). "
                        "The built-in voices need neither."
                    )
                last = next((line.strip() for line in reversed(stderr.strip().splitlines()) if line.strip()), "")
                raise ValueError(f"{ENGINES[body.engine]['name']} could not run. " + last[:160])
            voice = "cloned" if reference else body.voice
            return {"media": ingest_path(output, body.text[:40] + ".wav", {"source": body.engine, "voice": voice})}
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            output.unlink(missing_ok=True)
            if reference:
                Path(reference).unlink(missing_ok=True)

    return jobs.submit("speech", operation)


@router.post("", status_code=202)
def speak(body: SpeechInput):
    if body.engine not in ENGINES:
        raise HTTPException(422, f"Unknown speech engine {body.engine!r}")
    if body.engine != "kokoro":
        return _speak_with(body)
    if not ready("local-speech"):
        raise HTTPException(409, "Download Kokoro in Local models first")
    python = interpreter()
    if not python:
        raise HTTPException(409, "Run setup_local_ai to install the external speech runtime")

    def operation(job_id, report, cancelled):
        output = DATA_DIR / "speech" / (job_id + ".wav")
        output.parent.mkdir(parents=True, exist_ok=True)
        args = {
            **body.model_dump(),
            "model": str(ROOT / "kokoro-v1.0.onnx"),
            "voices": str(ROOT / "voices-v1.0.bin"),
            "output": str(output),
        }
        process = subprocess.Popen(
            [python, "-c", WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_worker_env()
        )
        try:
            _stdout, stderr = communicate(process, json.dumps(args), timeout=600, cancelled=cancelled)
            if cancelled():
                raise InterruptedError("Cancelled")
            if process.returncode:
                print("local speech worker failed:\n" + stderr[-2000:], file=sys.stderr, flush=True)
                last = next((line.strip() for line in reversed(stderr.strip().splitlines()) if line.strip()), "")
                raise ValueError("Local speech could not run. " + last[:160])
            return {"media": ingest_path(output, body.text[:40] + ".wav", {"source": "kokoro", "voice": body.voice})}
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
            output.unlink(missing_ok=True)

    return jobs.submit("speech", operation)
