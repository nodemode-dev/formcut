import json
import os
import shutil
import sys


def resource_dir() -> str:
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


def selfcheck() -> int:
    info = {"python": sys.version.split()[0]}
    for name in ("fastapi", "uvicorn", "python_multipart", "PIL", "cv2", "wgpu", "onnxruntime", "grpc", "mcp"):
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
    except ImportError as exc:
        info["native_kernels"] = False
        info["native_error"] = f"{type(exc).__name__}: {exc}"
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
    if "--mcp" in sys.argv:
        # An MCP client launched this process: stdout is the protocol from here on.
        from app.agent_mcp import main as agent_server

        agent_server()
        return 0
    os.environ.setdefault("FORMCUT_DIST", os.path.join(resource_dir(), "frontend_dist"))
    import uvicorn

    from app.main import app as fastapi_app

    import logging
    import socket

    from app.discovery import publish, withdraw
    from app.main import APP_VERSION

    # The socket is bound here, so the port is known before the server starts and
    # can be published for agents (app/discovery.py).
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", int(os.environ.get("FORMCUT_PORT", "0") or 0)))
    port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}"

    class Server(uvicorn.Server):
        # Given a bound socket, uvicorn does not print its address, and the app
        # finds its engine by that line, so it is printed here, the same way, once
        # the server is listening. The record is withdrawn during shutdown, because
        # uvicorn then re-raises the stop signal and no atexit handler would run.
        async def startup(self, sockets=None):
            await super().startup(sockets=sockets)
            if self.started:
                logging.getLogger("uvicorn.error").info("Uvicorn running on %s (Press CTRL+C to quit)", url)

        async def shutdown(self, sockets=None):
            await super().shutdown(sockets=sockets)
            withdraw()

    publish(url, APP_VERSION)
    Server(uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="info")).run(sockets=[listener])
    return 0


if __name__ == "__main__":
    sys.exit(main())
