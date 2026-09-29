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


def submit(kind: str, operation) -> dict:
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
        job_id = uuid.uuid4().hex
        _jobs[job_id] = {
            "id": job_id,
            "kind": kind,
            "status": "queued",
            "progress": 0.0,
            "cancel": threading.Event(),
            "created": time.time(),
        }

    def run():
        try:
            with _lock:
                job = _jobs[job_id]
                job["status"] = "running"
            publish("job", job=job_id, job_kind=kind, status="running", progress=0.0)
            last_announced = 0.0

            def report(value, message=None, **fields):
                nonlocal last_announced
                with _lock:
                    job["progress"] = min(0.99, max(0, float(value)))
                    if message is not None:
                        job["message"] = str(message)[:200]  # what the job is doing, beside the fraction
                    # what a long job has made so far (a continuous generation's pictures), for the page to show
                    job.update({key: value for key, value in fields.items() if key in ("made", "seeds", "notes", "warning", "timing")})
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
