"""Running a local image model's process: real progress, a real cancel, and memory kept in hand.

Krea 2 and FLUX.2 [klein] run in a process of their own (mflux on Apple silicon, diffusers elsewhere). Until v2.0.7
that process was waited on in silence: the job stood at 0% until the picture appeared, a cancel only stopped the
page from asking, and two pictures asked for at once loaded two models of 10 to 22 GB side by side.

- run(): the process's output is read as it comes. Both mflux and diffusers draw their denoising progress with tqdm
  ("3/8 [00:04<00:06, ...]"), which gives the step; before the first step the job says it is loading the model, after
  the last that it is finishing the picture. A cancel ends the process (terminate, then kill) and the job is
  cancelled; a process that runs past its time limit is ended and reported with the end of its output.
- plan(): what the machine's memory allows: mflux's --low-ram (the model's parts loaded as they are needed and let go
  after) when the model would take more than about half the memory, or when the person asks for it; and a cap on
  MLX's cache (--mlx-cache-limit-gb), so the editor beside it keeps its room.
- HEAVY: one local image model runs at a time; a second picture waits for the first, and says so.
"""

from __future__ import annotations

import os
import queue
import re
import subprocess
import threading
import time
from collections import deque

HEAVY = threading.Lock()
STEP = re.compile(rb"(\d+)/(\d+) \[")
TIME_LIMIT = float(os.environ.get("FORMCUT_LOCAL_IMAGE_TIMEOUT", "3600"))


def total_memory() -> int:
    """This machine's memory in bytes (0 when it cannot be read)."""
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (ValueError, OSError, AttributeError):
        return 0


def plan(model_bytes: int, mode: str = "auto") -> dict:
    """Memory settings for one run. mode: "auto" (low-RAM when the model would take more than about half the memory),
    "low" (always), or "normal" (never)."""
    memory = total_memory()
    low = mode == "low" or (mode == "auto" and memory > 0 and model_bytes * 2 > memory)
    cache = max(1.0, round(memory / 1e9 * 0.1, 1)) if memory else 4.0
    return {"lowRam": low, "cacheLimitGb": cache, "memoryGb": round(memory / 1e9, 1), "modelGb": round(model_bytes / 1e9, 1)}


def mflux_memory_flags(settings: dict) -> list[str]:
    return [*(["--low-ram"] if settings["lowRam"] else []), "--mlx-cache-limit-gb", f"{settings['cacheLimitGb']:g}"]


def run(command: list[str], steps: int, report, cancelled, label: str, env: dict | None = None, time_limit: float = TIME_LIMIT) -> str:
    """Run a model's process to its end, reporting progress; returns the end of its output. Raises InterruptedError
    on cancel and RuntimeError on a failure or a time-out."""
    say = _say(report)
    if not HEAVY.acquire(blocking=False):
        say(0.0, "Waiting for the picture before it to finish")
        while not HEAVY.acquire(timeout=0.25):
            if cancelled():
                raise InterruptedError("cancelled")
    try:
        return _run(command, steps, say, cancelled, label, env, time_limit)
    finally:
        HEAVY.release()


def _say(report):
    def say(value: float, message: str | None = None) -> None:
        try:
            report(value, message)
        except TypeError:  # a report that takes only the fraction
            report(value)

    return say


def _run(command, steps, say, cancelled, label, env, time_limit) -> str:
    say(0.02, f"Loading {label}")
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env={**os.environ, **(env or {}), "PYTHONUNBUFFERED": "1", "TQDM_MININTERVAL": "0.2"},
    )
    chunks: queue.Queue = queue.Queue()
    reader = threading.Thread(target=_pump, args=(process.stdout, chunks), daemon=True)
    reader.start()
    tail: deque = deque(maxlen=60)
    started, last_step, loading = time.time(), -1, 0.02
    pending = b""
    try:
        while True:
            try:
                chunk = chunks.get(timeout=0.2)
            except queue.Empty:
                chunk = b""
            if chunk is None:
                break
            if chunk:
                pending += chunk
                *lines, pending = re.split(rb"[\r\n]", pending)
                for line in lines:
                    if line.strip():
                        tail.append(line.decode("utf-8", "replace"))
                    found = STEP.findall(line)
                    for raw_done, raw_total in found:
                        done, total = int(raw_done), int(raw_total)
                        if total == steps and done != last_step:
                            last_step = done
                            say(0.1 + 0.85 * done / max(1, total), f"Step {done} of {total}" if done < total else "Finishing the picture")
            elif last_step < 0:
                # loading can take a minute on the first run: the bar creeps so the page is seen to be alive
                loading = min(0.09, loading + 0.0005)
                say(loading, f"Loading {label}")
            if cancelled():
                _end(process)
                raise InterruptedError("cancelled")
            if time.time() - started > time_limit:
                _end(process)
                raise RuntimeError(f"{label} ran past {int(time_limit / 60)} minutes and was stopped: " + "\n".join(list(tail)[-8:]))
        process.wait()
    finally:
        if process.poll() is None:
            _end(process)
    if pending.strip():
        tail.append(pending.decode("utf-8", "replace"))
    text = "\n".join(tail)
    if process.returncode:
        raise RuntimeError(f"{label} did not make a picture: " + text[-600:])
    say(0.96, "Finishing the picture")
    return text


def _pump(stream, chunks: queue.Queue) -> None:
    for chunk in iter(lambda: stream.read1(4096) if hasattr(stream, "read1") else stream.read(4096), b""):
        chunks.put(chunk)
    chunks.put(None)


def _end(process) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
