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
    """Memory settings for one run, costing as little speed as the machine allows. mode "auto": mflux runs as it would
    from the command line, with the decode tiled when the model and an untiled decode (about 7 GB at 1024 px for Krea
    2) would not fit beside each other, and --low-ram (with a capped MLX cache) only when the model itself would not
    fit, as both cost a great deal of time; "low": --low-ram and the capped cache always; "normal": neither, nor
    tiling. (Until 2.1.7, auto took --low-ram whenever the model was over half the memory and always capped the cache
    at a tenth of it: on a 24 GB Mac with a 4-bit Krea 2, a picture took nearly twice what mflux takes alone.)"""
    memory = total_memory()
    low = mode == "low" or (mode == "auto" and memory > 0 and model_bytes > memory * 0.75)
    cache = max(1.0, round(memory / 1e9 * 0.1, 1)) if low and memory else None
    tiling = not low and mode == "auto" and memory > 0 and model_bytes + 8e9 > memory * 0.9
    return {
        "lowRam": low,
        "vaeTiling": tiling,
        "cacheLimitGb": cache,
        "memoryGb": round(memory / 1e9, 1),
        "modelGb": round(model_bytes / 1e9, 1),
    }


def mflux_memory_flags(settings: dict) -> list[str]:
    flags = ["--low-ram"] if settings["lowRam"] else []
    if settings.get("cacheLimitGb"):
        flags += ["--mlx-cache-limit-gb", f"{settings['cacheLimitGb']:g}"]
    return flags


def run(
    command: list[str],
    steps: int,
    report,
    cancelled,
    label: str,
    env: dict | None = None,
    time_limit: float = TIME_LIMIT,
    images: int = 1,
    on_tick=None,
    continuous: bool = False,
    on_next=None,
) -> str:
    """on_tick is called several times a second while the model runs (a continuous session collects its pictures
    there); continuous shows each picture's own progress rather than the share of all, and has no time limit."""
    """Run a model's process to its end, reporting progress; returns the end of its output. Raises InterruptedError
    on cancel and RuntimeError on a failure or a time-out."""
    terminal = _Terminal(label)
    terminal.start(command)
    say = _say(report, terminal)
    if not HEAVY.acquire(blocking=False):
        say(0.0, "Waiting for the picture before it to finish")
        while not HEAVY.acquire(timeout=0.25):
            if cancelled():
                raise InterruptedError("cancelled")
    outcome = "stopped"
    try:
        text = _run(
            command,
            steps,
            say,
            cancelled,
            label,
            {**terminal.columns(), **(env or {})},
            float("inf") if continuous else time_limit,
            images,
            on_tick,
            continuous,
            terminal,
            on_next,
        )
        outcome = "done"
        return text
    except InterruptedError:
        outcome = "cancelled"
        raise
    finally:
        HEAVY.release()
        terminal.end(outcome)


class _Terminal:
    """The terminal the engine was started from, shown the model's own output as it comes: mflux's tqdm bar (its
    steps, the time elapsed and left, its/s) redrawn in place, sized to the terminal, not a bar of formcut's; a
    line when the run starts and one when it ends. FORMCUT_QUIET_PROGRESS=1 keeps it all out."""

    def __init__(self, label: str):
        import sys

        self.label, self.stream = label, sys.__stderr__
        self.quiet = self.stream is None or os.environ.get("FORMCUT_QUIET_PROGRESS") == "1"
        self.started = time.time()

    def columns(self) -> dict:
        """COLUMNS and LINES for the model's process, so tqdm draws its bar to this terminal's width."""
        import shutil

        try:
            size = os.get_terminal_size(self.stream.fileno())
        except (OSError, AttributeError, ValueError):
            size = shutil.get_terminal_size((100, 24))
        return {"COLUMNS": str(size.columns), "LINES": str(size.lines)}

    def _write(self, data: bytes) -> None:
        if self.quiet:
            return
        try:
            target = getattr(self.stream, "buffer", None)
            if target is not None:
                target.write(data)
            else:
                self.stream.write(data.decode("utf-8", "replace"))
            self.stream.flush()
        except (OSError, ValueError):
            pass

    def start(self, command: list[str] | None = None) -> None:
        # the command itself, as it would be typed, so a run can be set beside mflux run by hand
        import shlex

        shown = f"\n  {shlex.join(command)}" if command else ""
        self._write(f"formcut: {self.label}{shown}\n".encode())

    def show(self, chunk: bytes) -> None:
        self._write(chunk)

    def end(self, outcome: str) -> None:
        self._write(f"\nformcut: {self.label}: {outcome} in {time.time() - self.started:.1f} s\n".encode())


# tqdm's own meter: "4/8 [00:05<00:05,  1.30s/it]" (or it/s; "?" before a rate is known)
METER = re.compile(rb"(\d+)/(\d+) \[([\d:]+)<([\d:?]+),\s*([\d.?]+)\s*(s/it|it/s)\]")


def _say(report, terminal: _Terminal | None = None):
    def say(value: float, message: str | None = None, **fields) -> None:
        try:
            report(value, message, **fields)
        except TypeError:  # a report that takes only the fraction (and perhaps the message)
            try:
                report(value, message)
            except TypeError:
                report(value)

    return say


def _run(
    command, steps, say, cancelled, label, env, time_limit, images=1, on_tick=None, continuous=False, terminal=None, on_next=None
) -> str:
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
    started, last_step, loading, image = time.time(), -1, 0.02, 0
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
                if terminal is not None:
                    terminal.show(chunk)  # the model's own output, its tqdm bar included, as it comes
                pending += chunk
                *lines, pending = re.split(rb"[\r\n]", pending)
                for line in lines:
                    if line.strip():
                        tail.append(line.decode("utf-8", "replace"))
                    meter = METER.search(line)
                    timing = None
                    if meter:
                        # tqdm's own reading: elapsed, left and the rate, for the page to show as tqdm does
                        elapsed, left, rate, unit = (part.decode() for part in meter.group(3, 4, 5, 6))
                        timing = {
                            "elapsed": elapsed,
                            "remaining": left,
                            "rate": f"{rate}{unit}",
                            "step": int(meter.group(1)),
                            "steps": int(meter.group(2)),
                        }
                    found = STEP.findall(line)
                    for raw_done, raw_total in found:
                        done, total = int(raw_done), int(raw_total)
                        if total == steps and timing and done == last_step:
                            say(
                                0.1 + 0.85 * ((image if not continuous else 0) + done / max(1, total)) / (1 if continuous else images),
                                None,
                                timing=timing,
                            )
                        if total == steps and done != last_step:
                            if done < last_step and image + 1 < images:
                                image += 1  # the next seed's picture: mflux draws its steps again from 0
                                if on_next is not None:
                                    on_next()  # the picture before it is written: it is taken now, before this one goes on
                            last_step = done
                            stage = f"Step {done} of {total}" if done < total else "Finishing the picture"
                            extra = {"timing": timing} if timing else {}
                            if continuous:
                                say(0.1 + 0.85 * done / max(1, total), f"Picture {image + 1}: {stage}", **extra)
                            else:
                                if images > 1:
                                    stage = f"Picture {image + 1} of {images}: {stage}"
                                say(0.1 + 0.85 * (image + done / max(1, total)) / images, stage, **extra)
            elif last_step < 0:
                # loading can take a minute on the first run: the bar creeps so the page is seen to be alive, and
                # the time loading has taken goes with it
                loading = min(0.09, loading + 0.0005)
                waited = int(time.time() - started)
                say(loading, f"Loading {label}", timing={"elapsed": f"{waited // 60:02d}:{waited % 60:02d}", "loading": True})
            if on_tick is not None:
                on_tick()
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
