import json
import os
import shutil
import sys


def resource_dir() -> str:
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def selfcheck() -> int:
    info = {"python": sys.version.split()[0]}
    for name in ("fastapi", "uvicorn", "multipart", "PIL", "cv2", "wgpu", "onnxruntime", "grpc"):
        try:
            mod = __import__(name)
            info[name] = getattr(mod, "__version__", "ok")
        except Exception as exc:
            info[name] = f"missing: {exc}"
    from app.main import APP_VERSION

    info["formcut"] = APP_VERSION
    info["dist_bundled"] = os.path.isdir(os.path.join(resource_dir(), "frontend_dist"))
    info["ffmpeg_on_path"] = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
    # formcut's Rust kernels: without them every render still works, on NumPy, several
    # times slower, so a build script can refuse an engine frozen without them.
    try:
        import formcut_native  # noqa: F401

        info["native_kernels"] = True
    except ImportError:
        info["native_kernels"] = False
    print(json.dumps(info))
    return 1 if any(str(value).startswith("missing:") for value in info.values()) or (getattr(sys, "frozen", False) and not info["dist_bundled"]) else 0


def main() -> int:
    if "--headless" in sys.argv:
        sys.argv.remove("--headless")
        from app.cli import main as headless
        headless()
        return 0
    if "--selfcheck" in sys.argv:
        return selfcheck()
    os.environ.setdefault("FORMCUT_DIST", os.path.join(resource_dir(), "frontend_dist"))
    import uvicorn

    from app.main import app as fastapi_app

    port = int(os.environ.get("FORMCUT_PORT", "0") or 0)
    uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
