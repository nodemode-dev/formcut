import json
import os
import subprocess
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import jobs
from .media import ingest_path
from .model_manager import ROOT, ready
from .paths import DATA_DIR
from .processes import communicate

router = APIRouter(prefix="/api/speech", tags=["speech"])
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


@router.get("/voices")
def voices():
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


@router.post("", status_code=202)
def speak(body: SpeechInput):
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
        process = subprocess.Popen([python, "-c", WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
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
