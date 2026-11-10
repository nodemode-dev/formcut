"""Each function call runs in a child process with an empty data folder of its own.

The engine fixes its data folder (library, assets, project store, renders) when its modules are first imported, and
every module keeps its own copy of the paths, so it cannot be swapped inside a running process. The entries therefore
check their params and inputs here, then run the work in `python -m app.functions _here` with FORMCUT_DATA_DIR set to
a fresh temporary folder, removed afterwards. Whatever the work looks up by id can only find what this call brought,
never a person's library or a container's, and this process's environment is never changed. The models folder is
passed through, so a Whisper model fetched once stays fetched.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from .contract import FunctionError, checked_params, input_file, output_dir, spec

BACKEND = Path(__file__).resolve().parents[2]
FAILED = 3  # the child's exit status for a FunctionError, its message on stdout as {"error": ...}


def run_isolated(function_id: str, inputs: dict, params: dict, out_dir: str) -> dict:
    checked_params(function_id, params)
    inputs = {i["name"]: str(input_file(inputs, i["name"])) for i in spec(function_id)["inputs"]}
    folder = output_dir(out_dir)
    private = tempfile.mkdtemp(prefix="formcut-function-")
    try:
        command = [sys.executable, "-m", "app.functions", "_here", function_id]
        command += ["--inputs", json.dumps(inputs), "--params", json.dumps(params or {}), "--out", str(folder)]
        # A session of its own, so a timeout ends the child and every ffmpeg it started (one may ignore SIGTERM).
        child = subprocess.Popen(
            command,
            cwd=BACKEND,
            env=_child_env(private),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=os.name != "nt",
        )
        limit = spec(function_id)["timeout_s"]
        try:
            stdout, stderr = child.communicate(timeout=limit)
        except subprocess.TimeoutExpired as exc:
            _kill(child)
            raise FunctionError(f"{function_id} did not finish within {limit} s") from exc
    finally:
        shutil.rmtree(private, ignore_errors=True)
    return _result(function_id, subprocess.CompletedProcess(command, child.returncode, stdout, stderr))


def _kill(child: subprocess.Popen) -> None:
    if os.name != "nt":
        with contextlib.suppress(ProcessLookupError):
            os.killpg(child.pid, signal.SIGKILL)
    else:
        child.kill()
    child.communicate()


def _child_env(private: str) -> dict:
    from ..paths import MODELS_DIR

    env = {**os.environ, "FORMCUT_DATA_DIR": private, "FORMCUT_MODELS_DIR": str(MODELS_DIR), "FORMCUT_NO_WARM": "1"}
    env["PYTHONPATH"] = os.pathsep.join(p for p in (str(BACKEND), os.environ.get("PYTHONPATH", "")) if p)
    return env


def _result(function_id: str, done: subprocess.CompletedProcess) -> dict:
    lines = done.stdout.strip().splitlines()
    try:
        reply = json.loads(lines[-1]) if lines else None
    except ValueError:
        reply = None
    if done.returncode == 0 and isinstance(reply, dict):
        return reply
    if done.returncode == FAILED and isinstance(reply, dict) and "error" in reply:
        raise FunctionError(str(reply["error"]))
    tail = [line for line in done.stderr.strip().splitlines() if line.strip()]
    raise FunctionError(f"{function_id} stopped unexpectedly: {tail[-1] if tail else f'exit status {done.returncode}'}")
