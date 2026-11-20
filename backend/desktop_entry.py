import contextlib
import json
import logging
import os
import shutil
import sys
from pathlib import Path

RECORDS_SINCE = (2, 18, 0)

if sys.stdin is None:
    sys.stdin = open(os.devnull, encoding="utf-8")
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")


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
    # PyAV, the in-process decoder: without it the engine falls back to ffmpeg pipes,
    # so it is reported, and setup/build_release refuses a Windows engine without it.
    try:
        import av

        info["pyav"] = av.__version__
    except ImportError as exc:
        info["pyav"] = False
        info["pyav_error"] = f"{type(exc).__name__}: {exc}"
    print(json.dumps(info))
    return 1 if any(str(value).startswith("missing:") for value in info.values()) or (getattr(sys, "frozen", False) and not info["dist_bundled"]) else 0


USAGE = """usage: formcut-engine [option]

Starts the formcut engine on 127.0.0.1 (the port is FORMCUT_PORT, or any free one) and serves the window.

options:
  --help, -h     print this and exit
  --version      print the engine's version and exit
  --selfcheck    report the bundled libraries as JSON and exit (1 when one is missing)
  --headless     run a command-line framing of the engine's API (see --headless --help)
  --bench        measure the frame rate of the CPU and device paths on this machine
  --mcp          serve formcut's MCP tools over stdio to an MCP client
"""


def main() -> int:
    if sys.argv[1:2] in (["--help"], ["-h"]):
        print(USAGE, end="")
        return 0
    if sys.argv[1:2] == ["--version"]:
        from app.main import APP_VERSION

        print(f"formcut-engine {APP_VERSION}")
        return 0
    if "--headless" in sys.argv:
        sys.argv.remove("--headless")
        from app.cli import main as headless
        headless()
        return 0
    if "--selfcheck" in sys.argv:
        return selfcheck()
    if "--bench" in sys.argv:
        # The frame-rate reading, TEST_PLAN 24: both paths on this machine's adapter.
        from app.bench import main as bench

        return bench(sys.argv[sys.argv.index("--bench") + 1 :])
    if "--mcp" in sys.argv:
        # An MCP client launched this process: stdout is the protocol from here on.
        from app.agent_mcp import main as agent_server

        agent_server()
        return 0
    try:
        return serve()
    except Exception:
        logging.getLogger("formcut").exception("the engine stopped on an error")
        raise


def give_up(record: Path) -> None:
    from app import startup

    if startup.read_lock(record).get("pid") == os.getpid():
        with contextlib.suppress(OSError):
            record.unlink()


def released_engine(data: Path) -> dict:
    import datetime

    try:
        found = json.loads((data / "engine.json").read_text(encoding="utf-8"))
        version = tuple(int(part) for part in str(found["version"]).split(".")[:3])
        started = datetime.datetime.fromisoformat(found["started"]).timestamp()
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    return {"pid": found.get("pid"), "started": started} if version < RECORDS_SINCE else {}


def hold_folder(data: Path, shell: int) -> Path:
    from app import jobs, startup

    log = logging.getLogger("formcut")
    record, replaced = startup.claim(data, shell)
    if replaced:
        log.info("an engine left running on %s was stopped (process %s)", data, replaced)
    if jobs.claim_data_dir():
        return record
    old = released_engine(data)
    state = startup.holder(old, shell > 0)
    held = startup.number(old.get("pid")) if state != startup.FREE else 0
    if state == startup.LEFTOVER and startup.end(held) and jobs.claim_data_dir():
        log.info("an engine from before 2.18.0 left running on %s was stopped (process %s)", data, held)
        return record
    give_up(record)
    who = f"engine process {held}" if held else "its engine recorded no process id"
    raise startup.Busy(f"formcut is already running on {data} ({who}).")


def watch_shell(record: Path, shell: int) -> None:
    from app import startup
    from app.discovery import withdraw

    if shell <= 1:
        return

    def leave() -> None:
        logging.getLogger("formcut").info("the app that started this engine is gone (process %s), stopping", shell)
        withdraw()
        give_up(record)
        os._exit(0)

    startup.watch(shell, leave)


def serve() -> int:
    os.environ.setdefault("FORMCUT_DIST", os.path.join(resource_dir(), "frontend_dist"))
    from app import startup
    from app.paths import DATA_DIR

    try:
        (DATA_DIR / "logs").mkdir(parents=True, exist_ok=True)
    except OSError as err:
        print(f"formcut cannot use its data folder: {err}", file=sys.stderr)
        return 5
    import uvicorn

    from app.main import LOGS
    from app.main import app as fastapi_app

    startup.keep_errors(LOGS)
    log = logging.getLogger("formcut")
    if startup.alone():
        beside = startup.app_beside(Path(sys.executable))
        if beside is not None and startup.open_app(beside):
            log.info("started without its app, so it opened %s and stopped", beside)
            return 0
        log.error("started without its app, and no app program was found near %s", sys.executable)
        print("formcut-engine is a part of FormCut and serves nothing on its own. Open FormCut instead.", file=sys.stderr)
        return 4
    shell = startup.shell_pid()
    try:
        record = hold_folder(DATA_DIR, shell)
    except startup.Busy as err:
        log.error("%s", err)
        print(err, file=sys.stderr)
        return 2
    watch_shell(record, shell)
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
            give_up(record)

    from app import window_key

    if window_key.stdout_mode():
        sys.stdout.write(f"{window_key.LINE}{window_key.KEY}\n")
        sys.stdout.flush()
    publish(url, APP_VERSION)
    Server(uvicorn.Config(fastapi_app, host="127.0.0.1", port=port, log_level="info", timeout_graceful_shutdown=3)).run(sockets=[listener])
    return 0


if __name__ == "__main__":
    sys.exit(main())
