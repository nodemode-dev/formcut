import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from .brush import router as brush_router
from .cloud import router as cloud_router
from .features import router as features_router
from .instagram import router as instagram_router
from .library import router as library_router
from .media import router as media_router
from .paths import DATA_DIR
from .presets import router as presets_router
from .projects import router as projects_router
from .remote import resume as resume_remote
from .remote import router as remote_router
from .security import LocalOnly
from .stock import router as stock_router
from .tiktok import router as tiktok_router

# The bundled ffmpeg, if there is one, goes to the front of the search path so
# a binary a person has replaced is the one that runs.
from .tools import prefer_bundled
from .track import router as track_router
from .tts import router as tts_router
from .upscale import router as upscale_router
from .webhooks import router as webhooks_router

prefer_bundled()

APP_VERSION = "1.19.0"

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
    from .ffmpeg_fetch import auto_fetch
    from .model_manager import auto_download

    auto_fetch()
    auto_download()


app.add_middleware(LocalOnly)
app.include_router(projects_router)
app.include_router(media_router)
app.include_router(stock_router)
app.include_router(tts_router)
app.include_router(presets_router)
from .generate import router as generate_router

app.include_router(generate_router)
from .addons import router as addons_router

app.include_router(addons_router)
app.include_router(track_router)
app.include_router(features_router)
app.include_router(brush_router)
app.include_router(library_router)
app.include_router(upscale_router)
app.include_router(webhooks_router)
app.include_router(tiktok_router)
app.include_router(instagram_router)
app.include_router(cloud_router)
app.include_router(remote_router)
app.add_event_handler("startup", lambda: resume_remote(app))


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": APP_VERSION}


_dist = Path(os.environ.get("FORMCUT_DIST", ""))
if os.environ.get("FORMCUT_DIST") and _dist.is_dir():
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")

# P9: one log per run, the last ten kept, and a system-information summary that
# never carries a provider key.
LOGS = DATA_DIR / "logs"


def _start_log() -> Path:
    import datetime

    LOGS.mkdir(parents=True, exist_ok=True)
    existing = sorted(LOGS.glob("engine-*.log"))
    for old in existing[:-9]:
        old.unlink(missing_ok=True)
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d-%H%M%S")
    path = LOGS / f"engine-{stamp}.log"
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger("formcut").info("engine %s starting", APP_VERSION)
    return path


class _QuietRoutine(logging.Filter):
    """Keep the log for things that went wrong or that a person did.

    The preview polls for frames many times a second and each one was logged,
    so anything worth reading scrolled past in a second. Routine successful
    reads are dropped; everything that failed, and every write, is kept.
    """

    ROUTINE = (
        "/api/render/sessions/",
        "/api/media/",
        "/thumb",
        "/filmstrip",
        "/api/jobs/",
        "/api/catalogue",
        "/api/locales",
        "/api/proxies",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        line = record.getMessage()
        if " 200 " not in line and " 304 " not in line:
            return True  # errors always stay
        if '"GET ' not in line:
            return True  # writes always stay
        return not any(part in line for part in self.ROUTINE)


logging.getLogger("uvicorn.access").addFilter(_QuietRoutine())

RUN_LOG = _start_log()

from .effect_packages import reload as _reload_packages

_PACKAGE_STATE = _reload_packages()
logging.getLogger("formcut").info("effect packages: %s loaded, %s failed", len(_PACKAGE_STATE["loaded"]), len(_PACKAGE_STATE["failures"]))

SECRET_HINTS = ("key", "token", "secret", "password", "authorization")


@app.get("/api/locales")
def locales() -> dict:
    """P6: locale files dropped into the data directory, with missing keys named."""
    import json as _json
    import sys as _sys

    # Locales that ship with the app are read as well as ones a person dropped
    # in, otherwise a translation that ships is one nobody ever sees. A clone
    # keeps them in frontend/public; a frozen build carries the built interface
    # as frontend_dist, where Vite copied them.
    bundled = [Path(__file__).resolve().parents[2] / "frontend" / "public" / "locales"]
    if hasattr(_sys, "_MEIPASS"):
        bundled.append(Path(_sys._MEIPASS) / "frontend_dist" / "locales")
    folders = [f for f in (*bundled, DATA_DIR / "locales") if f.is_dir()]
    english: dict = {}
    base = Path(__file__).resolve().parents[2] / "frontend" / "src" / "i18n" / "en.json"
    if base.is_file():
        try:
            english = _json.loads(base.read_text(encoding="utf-8"))
        except ValueError:
            english = {}
    out = []
    seen: set[str] = set()
    for path in sorted(p for f in folders for p in f.glob("*.json")):
        if path.stem in seen:
            continue
        seen.add(path.stem)
        if path.is_file():
            try:
                data = _json.loads(path.read_text(encoding="utf-8"))
            except ValueError as exc:
                out.append({"code": path.stem, "error": f"not valid json ({exc})"})
                continue
            if not isinstance(data, dict):
                out.append({"code": path.stem, "error": "the file is not an object of keys"})
                continue
            missing = sorted(set(english) - set(data)) if english else []
            out.append(
                {
                    # A locale names itself, so a dropped-in language lists under its
                    # own name rather than a code the person does not recognise.
                    "code": path.stem,
                    "name": str(data.get("language.name") or path.stem),
                    "keys": len(data),
                    "missing": missing[:50],
                    "missingCount": len(missing),
                    "strings": data,
                }
            )
    return {"locales": out}


@app.get("/api/proxies/settings")
def proxy_settings() -> dict:
    from . import proxies
    from . import renderer as renderer_module

    return {"enabled": renderer_module.PROXIES_ENABLED, "size": proxies.DEFAULT_LONG_SIDE, "sizes": list(proxies.ALLOWED_SIZES)}


@app.post("/api/proxies/settings")
def set_proxy_settings(body: dict) -> dict:
    from . import proxies
    from . import renderer as renderer_module

    if "enabled" in body:
        renderer_module.PROXIES_ENABLED = bool(body["enabled"])
    if "size" in body:
        size = int(body["size"])
        if size not in proxies.ALLOWED_SIZES:
            raise HTTPException(422, "unknown proxy size")
        proxies.DEFAULT_LONG_SIDE = size
    return proxy_settings()


@app.get("/api/packages")
def packages() -> dict:
    """P3: loaded effect packages and, for Settings, any that failed with why."""
    from .effect_packages import entries, failures

    return {"packages": entries(), "failures": failures()}


@app.post("/api/packages/reload")
def packages_reload() -> dict:
    from .effect_packages import reload as reload_packages

    return reload_packages()


@app.get("/api/diagnostics")
def diagnostics() -> dict:
    """Version, platform, encoders and models present; never a provider key."""
    import platform

    from . import gpu
    from .encoders import status as encoder_status
    from .model_manager import MODELS, ready

    environment = {
        name: ("set" if value else "unset")
        for name, value in os.environ.items()
        if name.startswith("FORMCUT_") and any(hint in name.lower() for hint in SECRET_HINTS)
    }
    return {
        "version": APP_VERSION,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "gpu": gpu.status(),
        "encoders": encoder_status()["containers"],
        "models": {name: ready(name) for name in MODELS},
        "dataDir": str(DATA_DIR),
        "log": str(RUN_LOG),
        "logs": [p.name for p in sorted(LOGS.glob("engine-*.log"))],
        # Secret-shaped settings are reported as set or unset only; their values
        # never leave the engine, so a copied report can be pasted into an issue.
        "secrets": environment,
    }


@app.get("/api/diagnostics/log")
def diagnostics_log() -> Response:
    text = RUN_LOG.read_text(encoding="utf-8", errors="replace") if RUN_LOG.is_file() else ""
    return Response(text[-200000:], media_type="text/plain; charset=utf-8")
