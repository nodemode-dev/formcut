"""The embedded terminal: a real shell inside the editor.

A WebSocket at /api/terminal/ws opens the person's shell on a pseudo-terminal
(the POSIX pty; on Windows a plain pipe-driven cmd.exe, which has no resize
and no colours but does run claude and codex) and relays bytes both ways.
The shell starts with FORMCUT_URL, FORMCUT_MCP_COMMAND and FORMCUT_MCP_ARGS
in its environment, so an agent started in it can be pointed at this
engine's MCP server without leaving the app, and the same LocalOnly rule that
guards every route guards this one: the socket accepts only a loopback origin.
One shell per socket; closing the pane ends the shell.
"""

import asyncio
import contextlib
import json
import os
import shlex
import signal
import struct
import sys
import threading

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .agent_connect import server_command

router = APIRouter(prefix="/api/terminal", tags=["terminal"])
POSIX = os.name == "posix"


def _environment() -> dict:
    command, args = server_command()
    env = dict(os.environ)
    env["FORMCUT_URL"] = os.environ.get("FORMCUT_URL", "http://127.0.0.1:8040")
    env["FORMCUT_MCP_COMMAND"] = command
    env["FORMCUT_MCP_ARGS"] = " ".join(shlex.quote(a) for a in args)
    env["FORMCUT_MCP"] = " ".join(shlex.quote(a) for a in [command, *args])
    env.setdefault("TERM", "xterm-256color")
    env["COLORTERM"] = "truecolor"
    return env


def _shell() -> list[str]:
    if POSIX:
        shell = os.environ.get("SHELL") or "/bin/bash"
        return [shell, "-l"] if os.path.basename(shell) in ("bash", "zsh") else [shell]
    return [os.environ.get("COMSPEC", "cmd.exe")]


class Session:
    """One shell on one socket."""

    def __init__(self, cols: int, rows: int):
        self.cols, self.rows = max(20, min(400, cols)), max(5, min(200, rows))
        self.pid = None
        self.fd = None
        self.process = None
        if POSIX:
            import pty

            pid, fd = pty.fork()
            if pid == 0:
                os.chdir(os.path.expanduser("~"))
                os.execvpe(_shell()[0], _shell(), _environment())  # noqa: S606 the shell is the feature
            self.pid, self.fd = pid, fd
            self.resize(self.cols, self.rows)
        else:
            import subprocess

            self.process = subprocess.Popen(
                _shell(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=_environment(),
                cwd=os.path.expanduser("~"),
            )

    def resize(self, cols: int, rows: int) -> None:
        self.cols, self.rows = max(20, min(400, cols)), max(5, min(200, rows))
        if POSIX and self.fd is not None:
            import fcntl
            import termios

            fcntl.ioctl(self.fd, termios.TIOCSWINSZ, struct.pack("HHHH", self.rows, self.cols, 0, 0))

    def write(self, data: bytes) -> None:
        if POSIX and self.fd is not None:
            os.write(self.fd, data)
        elif self.process and self.process.stdin:
            self.process.stdin.write(data)
            self.process.stdin.flush()

    def read(self) -> bytes:
        if POSIX and self.fd is not None:
            return os.read(self.fd, 65536)
        if self.process and self.process.stdout:
            return self.process.stdout.read1(65536) if hasattr(self.process.stdout, "read1") else self.process.stdout.readline()
        return b""

    def close(self) -> None:
        if POSIX and self.pid:
            with contextlib.suppress(OSError):
                os.kill(self.pid, signal.SIGHUP)
            with contextlib.suppress(OSError):
                os.close(self.fd)
            with contextlib.suppress(OSError):
                os.waitpid(self.pid, os.WNOHANG)
        elif self.process:
            self.process.kill()


@router.get("/status")
def status() -> dict:
    from shutil import which

    return {
        "available": True,
        "pty": POSIX,
        "shell": _shell()[0],
        "claude": which("claude") is not None,
        "codex": which("codex") is not None,
        "mcp": _environment()["FORMCUT_MCP"],
    }


@router.websocket("/ws")
async def terminal(socket: WebSocket) -> None:
    await socket.accept()
    try:
        cols = int(socket.query_params.get("cols", "100"))
        rows = int(socket.query_params.get("rows", "30"))
    except ValueError:
        cols, rows = 100, 30
    session = Session(cols, rows)
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    stop = threading.Event()

    def pump() -> None:
        while not stop.is_set():
            try:
                data = session.read()
            except OSError:
                break
            if not data:
                break
            loop.call_soon_threadsafe(queue.put_nowait, data)
        loop.call_soon_threadsafe(queue.put_nowait, None)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()

    async def send() -> None:
        while True:
            data = await queue.get()
            if data is None:
                break
            await socket.send_text(data.decode("utf-8", errors="replace"))

    sender = asyncio.create_task(send())
    try:
        while True:
            message = await socket.receive_text()
            if message.startswith("{"):
                try:
                    control = json.loads(message)
                except ValueError:
                    control = {}
                if isinstance(control.get("resize"), list) and len(control["resize"]) == 2:
                    session.resize(int(control["resize"][0]), int(control["resize"][1]))
                    continue
            session.write(message.encode("utf-8"))
    except WebSocketDisconnect:
        pass
    finally:
        stop.set()
        session.close()
        sender.cancel()
        if sys.platform != "win32":
            reader.join(timeout=1)
