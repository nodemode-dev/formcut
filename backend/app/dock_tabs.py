"""Terminal tabs by id, for the family's shared dock.

A tab is a program on a pseudo-terminal that outlives the socket that shows
it: a plain shell, or Claude Code, Codex, Cursor's agent or Antigravity when the
program is found on this computer. The window opens, lists, restarts and closes tabs over
routes under /api/terminal/ (all of them the window's only, and closed to a
paired device), and attaches to one with a socket that replays the tab's
scrollback and then relays typed JSON frames both ways.

An agent tab gets its own tab token (agent_access.open_tab) in its program's
environment as FORMCUT_AGENT_TAB, and a private file (mode 0600, named by
FORMCUT_TAB_MCP_CONFIG) with the MCP entry formcut_tab, which holds the name
of that variable and never its value. The token is never on a command line,
a plain shell tab gets none, and it stops working when the program ends, when
the tab is restarted and when the tab is closed.

GET /api/terminal/agents says which agent programs are found, in one call.
"""

from __future__ import annotations

import asyncio
import codecs
import contextlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from . import agent_access, agent_lookup, terminal, window_key
from .agent_connect import server_command
from .paths import DATA_DIR

router = APIRouter(prefix="/api/terminal", tags=["terminal"])

MCP_NAME = "formcut_tab"
CONFIG_ENV = "FORMCUT_TAB_MCP_CONFIG"
FOLDER = DATA_DIR / "dock"
SCROLLBACK = 262144
BACKLOG = 512
MOST_TABS = 12
PROMPT_LIMIT = 4000
RESUME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,63}$")
KEPT_FROM_CHILD = ("FORMCUT_REMOTE_TOKEN", window_key.STDOUT_ENV, CONFIG_ENV)
REMOTE = "the terminal is open to the desktop only"
PROGRAMS = {
    "claude": {
        "bin": "claude",
        "title": "Claude Code",
        "install": agent_lookup.install("claude"),
        "key": "ANTHROPIC_API_KEY",
        "kept": (".claude", ".credentials.json"),
    },
    "codex": {
        "bin": "codex",
        "title": "Codex",
        "install": agent_lookup.install("codex"),
        "key": "OPENAI_API_KEY",
        "kept": (".codex", "auth.json"),
    },
    "cursor": {
        "bin": "cursor-agent",
        "title": "Cursor",
        "install": agent_lookup.install("cursor"),
        "key": "CURSOR_API_KEY",
        "kept": None,
    },
    "antigravity": {
        "bin": "agy",
        "title": "Antigravity",
        "install": agent_lookup.install("antigravity"),
        "key": "",
        "kept": None,
    },
}
KINDS = ("shell", *PROGRAMS)
OVERRIDES = {
    "claude": ("FORMCUT_CLAUDE_BIN",),
    "codex": ("FORMCUT_CODEX_BIN",),
    "cursor": ("FORMCUT_CURSOR_BIN",),
    "antigravity": ("FORMCUT_ANTIGRAVITY_BIN",),
}
OTHERWISE = ""
TAB_FOLDER = DATA_DIR / "agent-tabs" / "antigravity"

_lock = threading.Lock()
_tabs: dict[str, Tab] = {}


def _fail(status: int, code: str, message: str, **more) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message, **more})


def _desktop_only(scope) -> None:
    if scope.get("formcut.remote"):
        raise _fail(403, "refused", REMOTE)


def _child_env(tab: str = "") -> dict:
    env = terminal._environment(tab)
    for name in KEPT_FROM_CHILD:
        env.pop(name, None)
    return env


def agent_env(path: str | None = None, tab: str = "") -> dict:
    """The environment an agent program is checked and started with: the family's, on top of the terminal's own."""
    return agent_lookup.child_env(path, base=_child_env(tab), shell_timeout=10.0)


def located(kind: str, fresh: bool = False) -> agent_lookup.Found:
    """Where an agent program is and whether it starts, by the family's finder."""
    found = agent_lookup.find(kind, override_vars=OVERRIDES.get(kind, ()), shell_timeout=10.0, fresh=fresh)
    return agent_lookup.check(found, agent_env(found.path), 15.0, fresh)


def find(kind: str) -> str | None:
    """Where an agent program is, wherever the family's finder looks."""
    return located(kind).path


def usable(kind: str) -> agent_lookup.Found:
    """The program that starts, asked once more when the first look did not give one."""
    found = located(kind)
    return found if found.state == "runs" else located(kind, True)


def said(kind: str, found: agent_lookup.Found) -> str:
    return agent_lookup.sentence(found, PROGRAMS[kind]["install"], OTHERWISE)


def _mcp_file(folder: Path) -> Path:
    return folder / ".agents" / "mcp_config.json"


def _servers(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}") if path.exists() else {}
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        raise OSError(f"{path} is not an MCP servers file formcut can read, so it was left alone")
    return data


def _replace(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + f".part-{os.getpid()}")
    with os.fdopen(os.open(part, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w", encoding="utf-8") as file:
        file.write(json.dumps(data, indent=2) + "\n")
    os.replace(part, path)


def write_tab_entry(folder: Path, token: str) -> None:
    """The tab's own entry, formcut_tab, in <folder>/.agents/mcp_config.json, where Antigravity reads its MCP servers.

    Every other entry and key in the file is kept; the file is replaced whole and is the user's alone.
    """
    command, args = server_command()
    env = {agent_access.TAB_ENV: token}
    if os.environ.get("FORMCUT_ENGINE", "").strip():
        env["FORMCUT_ENGINE"] = os.environ["FORMCUT_ENGINE"].strip()
    path = _mcp_file(folder)
    data = _servers(path)
    data.setdefault("mcpServers", {})[MCP_NAME] = {"command": command, "args": args, "env": env}
    _replace(path, data)


def remove_tab_entry(folder: Path, token: str) -> None:
    """Takes the tab's entry out when the tab closes, only while it still carries this tab's token; nothing else is touched."""
    path = _mcp_file(folder)
    try:
        data = _servers(path)
        entry = data.get("mcpServers", {}).get(MCP_NAME)
        if not isinstance(entry, dict) or (entry.get("env") or {}).get(agent_access.TAB_ENV) != token:
            return
        del data["mcpServers"][MCP_NAME]
        _replace(path, data)
    except OSError:
        return


def _retire(kind: str, token: str) -> None:
    agent_access.close_tab(token)
    if kind == "antigravity" and token:
        remove_tab_entry(TAB_FOLDER, token)


def _signed_in(kind: str) -> bool | None:
    """True when a sign-in is plainly there; None when formcut cannot tell without running the program."""
    program = PROGRAMS[kind]
    if program["key"] and os.environ.get(program["key"], "").strip():
        return True
    if program["kept"]:
        with contextlib.suppress(OSError):
            if os.path.getsize(os.path.join(os.path.expanduser("~"), *program["kept"])) > 2:
                return True
    return None


def agent_status() -> dict:
    out: dict = {"contract": terminal.DOCK_CONTRACT}
    for kind, program in PROGRAMS.items():
        found = located(kind)
        runs = found.state == "runs"
        out[kind] = agent_lookup.answer(found, program["install"], OTHERWISE) | {
            "install": "" if runs else program["install"],
            "signedIn": _signed_in(kind) if runs else None,
            "title": program["title"],
        }
    return out


def _reap(pid: int) -> None:
    """Wait for a closed tab's program; one that ignored the hang-up is killed after a second."""
    for _ in range(20):
        try:
            done, _status = os.waitpid(pid, os.WNOHANG)
        except OSError:
            return
        if done:
            return
        time.sleep(0.05)
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        with contextlib.suppress(OSError):
            os.kill(pid, signal.SIGKILL)
    with contextlib.suppress(OSError):
        os.waitpid(pid, 0)


class Attachment:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        self.loop = loop
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=BACKLOG)

    def offer(self, message: dict | None) -> None:
        try:
            self.queue.put_nowait(message)
        except asyncio.QueueFull:
            while not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put_nowait(None)


class Tab:
    """One program on one pseudo-terminal, shown by any number of sockets."""

    def __init__(self, kind: str, cols: int, rows: int, prompt: str = "", resume: str = ""):
        self.id = secrets.token_urlsafe(9)
        self.kind = kind
        self.title = PROGRAMS[kind]["title"] if kind in PROGRAMS else "Terminal"
        self.cols, self.rows = cols, rows
        self.lock = threading.Lock()
        self.listeners: list[Attachment] = []
        self.scroll = ""
        self.alive = False
        self.code: int | None = None
        self.token = ""
        self.session: terminal.Session | None = None
        self.generation = 0
        self.folder = FOLDER / self.id
        self.start(prompt, resume)

    def describe(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "alive": self.alive,
            "kind": self.kind,
            "tip": os.path.expanduser("~"),
            "code": self.code,
        }

    def _config(self) -> str:
        command, args = server_command()
        env = {agent_access.TAB_ENV: "${" + agent_access.TAB_ENV + "}"}
        if os.environ.get("FORMCUT_ENGINE", "").strip():
            env["FORMCUT_ENGINE"] = os.environ["FORMCUT_ENGINE"].strip()
        body = {"mcpServers": {MCP_NAME: {"command": command, "args": args, "env": env}}}
        FOLDER.mkdir(parents=True, exist_ok=True)
        self.folder.mkdir(mode=0o700, exist_ok=True)
        path = self.folder / "mcp.json"
        with contextlib.suppress(OSError):
            path.unlink()
        handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(body, file, indent=2)
        return str(path)

    def _argv(self, path: str, config: str, prompt: str, resume: str) -> list[str]:
        argv = [path]
        if self.kind == "claude":
            argv += ["--mcp-config", config]
            if resume:
                argv += ["--resume", resume]
            if prompt:
                argv.append(prompt)
        elif self.kind == "codex":
            command, args = server_command()
            forwarded = [agent_access.TAB_ENV, "FORMCUT_ENGINE"]
            for key, value in (("command", command), ("args", args), ("env_vars", forwarded)):
                argv += ["-c", f"mcp_servers.{MCP_NAME}.{key}={json.dumps(value)}"]
        return agent_lookup.start_argv(argv)

    def start(self, prompt: str = "", resume: str = "") -> None:
        argv, token, path, own = None, "", None, None
        if self.kind in PROGRAMS:
            found = usable(self.kind)
            if found.state != "runs":
                raise LookupError(said(self.kind, found))
            path = found.path
            token = agent_access.open_tab()
            own = TAB_FOLDER if self.kind == "antigravity" else None
        env = agent_env(path, token) if path else _child_env(token)
        try:
            if self.kind in PROGRAMS:
                env[CONFIG_ENV] = self._config()
                argv = self._argv(path, env[CONFIG_ENV], prompt, resume)
            if own:
                write_tab_entry(own, token)
            session = terminal.Session(self.cols, self.rows, argv=argv, env=env, cwd=str(own) if own else None)
        except OSError:
            _retire(self.kind, token)
            raise
        with self.lock:
            self.generation += 1
            generation = self.generation
            self.session, self.token = session, token
            self.alive, self.code, self.scroll = True, None, ""
            self.cols, self.rows = session.cols, session.rows
        threading.Thread(target=self._pump, args=(session, generation, token), daemon=True).start()

    def _emit(self, message: dict, generation: int, text: str = "") -> None:
        with self.lock:
            if generation != self.generation:
                return
            if text:
                self.scroll = (self.scroll + text)[-SCROLLBACK:]
            for listener in self.listeners:
                listener.loop.call_soon_threadsafe(listener.offer, message)

    def _pump(self, session: terminal.Session, generation: int, token: str) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        while generation == self.generation:
            try:
                data = session.read()
            except (OSError, ValueError):
                break
            if not data:
                break
            text = decoder.decode(data)
            if text:
                self._emit({"type": "data", "data": text}, generation, text)
        _retire(self.kind, token)
        code = None
        for _ in range(40):
            with self.lock:
                if generation != self.generation or not (terminal.POSIX and session.pid):
                    break
                try:
                    pid, status = os.waitpid(session.pid, os.WNOHANG)
                except OSError:
                    break
                if pid:
                    code = os.waitstatus_to_exitcode(status)
                    with contextlib.suppress(OSError):
                        os.close(session.fd)
                    session.pid = None
                    break
            time.sleep(0.05)
        if session.process:
            with contextlib.suppress(subprocess.SubprocessError):
                code = session.process.wait(timeout=2)
        with self.lock:
            if generation != self.generation:
                return
            self.alive, self.code = False, code
            for listener in self.listeners:
                listener.loop.call_soon_threadsafe(listener.offer, {"type": "exit", "code": code})

    def _end(self) -> None:
        with self.lock:
            self.generation += 1
            session, token = self.session, self.token
            self.session, self.token, self.alive = None, "", False
        _retire(self.kind, token)
        if session is not None and terminal.POSIX and session.pid:
            pid, session.pid = session.pid, None
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGHUP)
            with contextlib.suppress(OSError):
                os.close(session.fd)
            threading.Thread(target=_reap, args=(pid,), daemon=True).start()
        elif session is not None:
            session.close()
        shutil.rmtree(self.folder, ignore_errors=True)

    def restart(self) -> None:
        self._end()
        with self.lock:
            self.scroll = ""
            for listener in self.listeners:
                listener.loop.call_soon_threadsafe(listener.offer, {"type": "restart"})
        self.start()

    def close(self) -> None:
        self._end()
        with self.lock:
            listeners, self.listeners = self.listeners, []
        for listener in listeners:
            listener.loop.call_soon_threadsafe(listener.offer, None)

    def attach(self, loop: asyncio.AbstractEventLoop) -> tuple[Attachment, dict]:
        listener = Attachment(loop)
        with self.lock:
            self.listeners.append(listener)
            first = {"type": "replay", "data": self.scroll, "alive": self.alive, "code": self.code, "cols": self.cols, "rows": self.rows}
        return listener, first

    def detach(self, listener: Attachment) -> None:
        with self.lock:
            if listener in self.listeners:
                self.listeners.remove(listener)

    def write(self, text: str) -> None:
        session = self.session
        if session is not None and self.alive:
            with contextlib.suppress(OSError, ValueError):
                session.write(text.encode("utf-8"))

    def resize(self, cols: int, rows: int) -> None:
        session = self.session
        if session is not None and self.alive:
            with contextlib.suppress(OSError, ValueError):
                session.resize(cols, rows)
                self.cols, self.rows = session.cols, session.rows


class OpenTab(BaseModel):
    kind: str = "shell"
    cols: int = 100
    rows: int = 30
    prompt: str = ""
    resume: str = ""


def _clear_stale() -> None:
    if not FOLDER.is_dir():
        return
    with _lock:
        live = set(_tabs)
    for entry in FOLDER.iterdir():
        if entry.name not in live:
            shutil.rmtree(entry, ignore_errors=True)


@router.get("/agents")
def agents(request: Request) -> dict:
    _desktop_only(request.scope)
    return agent_status()


@router.get("/tabs")
def list_tabs(request: Request) -> dict:
    _desktop_only(request.scope)
    with _lock:
        tabs = list(_tabs.values())
    return {"contract": terminal.DOCK_CONTRACT, "kinds": list(KINDS), "tabs": [tab.describe() for tab in tabs]}


@router.post("/tabs")
def open_tab(body: OpenTab, request: Request) -> dict:
    _desktop_only(request.scope)
    window_key.require(request)
    if body.kind not in KINDS:
        raise _fail(422, "unknownKind", f"kind must be one of {', '.join(KINDS)}")
    if body.resume and (body.kind != "claude" or not RESUME.match(body.resume)):
        raise _fail(422, "badResume", "resume is a Claude Code session id, for a Claude Code tab")
    if body.prompt and body.kind != "claude":
        raise _fail(422, "badPrompt", "prompt is a first message for a Claude Code tab")
    with _lock:
        count = len(_tabs)
    if count >= MOST_TABS:
        raise _fail(409, "busy", f"formcut keeps at most {MOST_TABS} terminal tabs open; close one first")
    _clear_stale()
    try:
        tab = Tab(body.kind, body.cols, body.rows, body.prompt[:PROMPT_LIMIT], body.resume)
    except LookupError as exc:
        raise _fail(409, "notInstalled", str(exc), install=PROGRAMS[body.kind]["install"]) from exc
    except OSError as exc:
        raise _fail(500, "unreachable", f"the program could not be started: {exc.__class__.__name__}") from exc
    with _lock:
        _tabs[tab.id] = tab
    return tab.describe()


@router.post("/tabs/{tab_id}/restart")
def restart_tab(tab_id: str, request: Request) -> dict:
    _desktop_only(request.scope)
    window_key.require(request)
    with _lock:
        tab = _tabs.get(tab_id)
    if tab is None:
        raise _fail(404, "gone", "that terminal tab has closed")
    try:
        tab.restart()
    except LookupError as exc:
        raise _fail(409, "notInstalled", str(exc), install=PROGRAMS[tab.kind]["install"]) from exc
    except OSError as exc:
        raise _fail(500, "unreachable", f"the program could not be started: {exc.__class__.__name__}") from exc
    return tab.describe()


@router.delete("/tabs/{tab_id}")
def close_tab(tab_id: str, request: Request) -> dict:
    _desktop_only(request.scope)
    window_key.require(request)
    with _lock:
        tab = _tabs.pop(tab_id, None)
    if tab is not None:
        tab.close()
    return {"ok": True}


@router.websocket("/tabs/{tab_id}/ws")
async def attach(socket: WebSocket, tab_id: str) -> None:
    if socket.scope.get("formcut.remote"):
        await socket.close(code=1008)
        return
    await socket.accept()
    with _lock:
        tab = _tabs.get(tab_id)
    if tab is None:
        await socket.send_text(json.dumps({"type": "gone"}))
        await socket.close()
        return
    listener, first = tab.attach(asyncio.get_running_loop())
    await socket.send_text(json.dumps(first))
    if not first["alive"]:
        await socket.send_text(json.dumps({"type": "exit", "code": first["code"]}))

    async def send() -> None:
        while True:
            message = await listener.queue.get()
            if message is None:
                with contextlib.suppress(RuntimeError, OSError, WebSocketDisconnect):
                    await socket.close()
                break
            await socket.send_text(json.dumps(message))

    sender = asyncio.create_task(send())
    try:
        while True:
            raw = await socket.receive_text()
            try:
                message = json.loads(raw)
            except ValueError:
                continue
            if not isinstance(message, dict):
                continue
            if message.get("type") == "input" and isinstance(message.get("data"), str):
                tab.write(message["data"])
            elif message.get("type") == "resize":
                with contextlib.suppress(TypeError, ValueError):
                    tab.resize(int(message.get("cols")), int(message.get("rows")))
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        tab.detach(listener)
        sender.cancel()
