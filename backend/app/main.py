import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .export import router as export_router
from .features import router as features_router
from .security import LocalOnly
from .brush import router as brush_router
from .media import router as media_router
from .projects import router as projects_router
from .stock import router as stock_router
from .presets import router as presets_router
from .track import router as track_router
from .tts import router as tts_router

APP_VERSION = "0.54.1"

app = FastAPI(title="formcut engine", version=APP_VERSION)


@app.on_event("startup")
async def _remember_loop() -> None:
    # Jobs publish events from worker threads, so the loop that owns the
    # subscriber queues is captured once here rather than guessed per call.
    import asyncio

    from .orchestration import remember_loop

    remember_loop(asyncio.get_running_loop())


@app.on_event("startup")
async def _prepare_models() -> None:
    from .model_manager import auto_download

    auto_download()

app.add_middleware(LocalOnly)
app.include_router(projects_router)
app.include_router(media_router)
app.include_router(export_router)
app.include_router(stock_router)
app.include_router(tts_router)
app.include_router(presets_router)
app.include_router(track_router)
app.include_router(features_router)
app.include_router(brush_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": APP_VERSION}


_dist = Path(os.environ.get("FORMCUT_DIST", ""))
if os.environ.get("FORMCUT_DIST") and _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
