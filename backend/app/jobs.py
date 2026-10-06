import contextlib
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .orchestration import publish

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
_lock = threading.RLock()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="formcut-job")
_jobs = {}
# Jobs survive an engine restart (the owner's Posh session lost renders to four sandbox restarts): each status change
# is written to a ledger with the job's recipe; on start, finished jobs whose output is still there come back, and a
# job caught mid-run is re-queued under its own id where a resumer for its kind can rebuild it, else marked interrupted.
RESUMERS: dict = {}  # kind -> recipe -> operation
_KEPT = ("id", "kind", "status", "progress", "created", "result", "error", "message", "recipe")


def _ledger_path() -> Path:
    from .paths import DATA_DIR

    return DATA_DIR / "jobs.json"


_resumed = False  # until resume_pending has run, the ledger on disk holds jobs not loaded yet


def _write_ledger() -> None:
    from .durable import read_json, write_json

    with _lock:
        rows = {key: {k: v for k, v in job.items() if k in _KEPT} for key, job in _jobs.items()}
        if not _resumed:  # a job submitted at start-up before the resume ran must not wipe the jobs still on disk
            on_disk = read_json(_ledger_path(), {}) or {}
            rows = {**{k: v for k, v in on_disk.items() if k not in rows}, **rows}
    with contextlib.suppress(OSError):  # a read-only data folder keeps jobs in memory only, as before
        write_json(_ledger_path(), rows)


_claim = None


def claim_data_dir() -> bool:
    """One engine per data folder: an exclusive lock on <data>/engine.lock, held for the engine's life.

    Two engines on one folder (the app opened twice, a second engine started beside a running one) each resumed the
    same interrupted export and wrote the same frames: one renamed the other's half-written frame, and that one's
    clean-up deleted the cache both were using. The second engine now stops before it resumes anything. Taking the
    claim again in the same process is a no-op."""
    global _claim
    if _claim is not None:
        return True
    from .paths import DATA_DIR

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(DATA_DIR / "engine.lock", "a+")  # noqa: SIM115 (held open for the engine's life)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _claim = handle
    return True


def resume_pending() -> dict:
    """On engine start: the ledger's finished jobs back where their output still exists, interrupted ones re-queued
    under their own ids where their kind has a resumer, the rest marked interrupted. Returns what it did."""
    from .durable import read_json

    rows = read_json(_ledger_path(), {}) or {}
    restored, resumed, interrupted = 0, 0, 0
    for key, row in rows.items():
        if key in _jobs or not isinstance(row, dict):
            continue
        if row.get("status") == "done":
            output = (row.get("result") or {}).get("file")
            if not output or Path(output).exists():
                _jobs[key] = {**row, "cancel": threading.Event()}
                restored += 1
        elif row.get("status") in ("queued", "running"):
            resumer = RESUMERS.get(row.get("kind"))
            reason = row.get("error") or "the engine restarted during this job; start it again"
            if resumer and row.get("recipe"):
                try:
                    submit(row["kind"], resumer(row["recipe"]), recipe=row["recipe"], job_id=key)
                    resumed += 1
                    continue
                except Exception as exc:  # a recipe that no longer builds: say so rather than drop it
                    reason = f"could not resume: {exc}"
            _jobs[key] = {**row, "status": "interrupted", "error": reason, "cancel": threading.Event()}
            interrupted += 1
        elif row.get("status") in ("error", "cancelled", "interrupted"):
            _jobs[key] = {**row, "cancel": threading.Event()}
    global _resumed
    _resumed = True
    _write_ledger()
    return {"restored": restored, "resumed": resumed, "interrupted": interrupted}


def submit(kind: str, operation, recipe: dict | None = None, job_id: str | None = None) -> dict:
    with _lock:
        active = sum(j["status"] in ("queued", "running") for j in _jobs.values())
        if active >= 8:
            raise HTTPException(429, "The local work queue is full")
        for key in list(_jobs):
            if len(_jobs) <= 100:
                break
            if _jobs[key]["status"] not in ("queued", "running"):
                output = _jobs[key].get("result", {}).get("file")
                if output:
                    Path(output).unlink(missing_ok=True)
                del _jobs[key]
        job_id = job_id or uuid.uuid4().hex
        _jobs[job_id] = {
            "id": job_id,
            "kind": kind,
            "status": "queued",
            "progress": 0.0,
            "cancel": threading.Event(),
            "created": time.time(),
            **({"recipe": recipe} if recipe else {}),
        }
    _write_ledger()

    def run():
        try:
            with _lock:
                job = _jobs[job_id]
                job["status"] = "running"
            _write_ledger()
            publish("job", job=job_id, job_kind=kind, status="running", progress=0.0)
            last_announced = 0.0

            def report(value, message=None, **fields):
                nonlocal last_announced
                with _lock:
                    if value is not None:  # None: the message or fields only, the bar left where it is
                        job["progress"] = min(0.99, max(0, float(value)))
                    if message is not None:
                        job["message"] = str(message)[:200]  # what the job is doing, beside the fraction
                    # what a long job has made so far (a continuous generation's pictures), for the page to show
                    job.update(
                        {
                            key: value
                            for key, value in fields.items()
                            if key in ("made", "seeds", "notes", "warning", "timing", "frame", "confidence")
                        }
                    )
                # Announce every five percent: enough for a progress bar without
                # flooding a subscriber on a long render.
                if job["progress"] - last_announced >= 0.05:
                    last_announced = job["progress"]
                    publish("job", job=job_id, job_kind=kind, status="running", progress=round(job["progress"], 3))

            result = operation(job_id, report, job["cancel"].is_set)
            with _lock:
                if job["cancel"].is_set():
                    job["status"] = "cancelled"
                    if result.get("file"):
                        Path(result["file"]).unlink(missing_ok=True)
                else:
                    job.update(status="done", progress=1, result=result)
            publish("job", job=job_id, job_kind=kind, status=_jobs[job_id]["status"], progress=1.0, file=(result or {}).get("file"))
        except InterruptedError:
            with _lock:
                _jobs[job_id]["status"] = "cancelled"
            publish("job", job=job_id, job_kind=kind, status="cancelled")
        except Exception as exc:
            with _lock:
                _jobs[job_id].update(status="error", error=str(exc))
            publish("job", job=job_id, job_kind=kind, status="error", error=str(exc))
        finally:
            _write_ledger()

    _pool.submit(run)
    return {"job_id": job_id}


@router.get("/{job_id}")
def status(job_id: str) -> dict:
    with _lock:
        if job_id not in _jobs:
            raise HTTPException(404, "Job not found")
        return {k: v for k, v in _jobs[job_id].items() if k != "cancel"}


@router.delete("/{job_id}")
def cancel(job_id: str) -> dict:
    with _lock:
        if job_id not in _jobs:
            raise HTTPException(404, "Job not found")
        _jobs[job_id]["cancel"].set()
    return {"cancel_requested": True}


@router.get("/{job_id}/file")
def file(job_id: str):
    item = status(job_id)
    result = item.get("result", {})
    if item["status"] != "done" or not result.get("file"):
        raise HTTPException(409, "Job output is not ready")
    return FileResponse(result["file"], filename=result.get("name", "formcut-output"), media_type=result.get("media_type"))
