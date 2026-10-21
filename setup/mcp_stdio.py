#!/usr/bin/env python3
"""./formcut mcp: formcut's MCP server over stdio, starting the engine when nothing answers.

The server is backend/app/agent_mcp.py (the installed app runs it as formcut-engine --mcp). This runs it from a
checkout with an interpreter that has the MCP SDK: the engine's backend/venv, else mcp/.venv. Before serving, it
asks the engine the server would drive (FORMCUT_ENGINE, else the running app's engine.json, else 127.0.0.1:8040);
when nothing answers and that is the source-run address, it starts the engine from backend/venv in the background
and waits for it. FORMCUT_MCP_NO_START=1 skips that. stdout is the MCP channel, so everything here writes to stderr.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
CANDIDATES = (
    BACKEND / "venv" / "bin" / "python",
    BACKEND / "venv" / "Scripts" / "python.exe",
    ROOT / "mcp" / ".venv" / "bin" / "python",
    ROOT / "mcp" / ".venv" / "Scripts" / "python.exe",
)
SOURCE_RUN = "http://127.0.0.1:8040"
LOG = Path(tempfile.gettempdir()) / "formcut-engine-mcp.log"


def say(text: str) -> None:
    print(f"[formcut mcp] {text}", file=sys.stderr, flush=True)


def ensure_sdk() -> None:
    """Run inside backend/venv (or mcp/.venv) whenever one exists: a system python may carry a different mcp, or
    none of the server's other dependencies."""
    if not os.environ.get("FORMCUT_MCP_REEXEC"):
        for python in CANDIDATES:
            venv = python.parent.parent
            if python.exists() and Path(sys.prefix).resolve() != venv.resolve():
                os.environ["FORMCUT_MCP_REEXEC"] = "1"
                os.execv(str(python), [str(python), __file__, *sys.argv[1:]])
            if python.exists():
                break
    try:
        import httpx  # noqa: F401
        import mcp  # noqa: F401
    except ImportError:
        sys.exit("[formcut mcp] no interpreter with the MCP SDK: run ./formcut once (it installs backend/venv), or mcp/oc_install")


def answers(base: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base}/api/health", timeout=2) as reply:
            return reply.status == 200
    except Exception:
        return False


def start_engine() -> None:
    python = next((p for p in CANDIDATES[:2] if p.exists()), None)
    if python is None:
        say("the engine is not installed (no backend/venv); run ./formcut once, then try again")
        return
    env = dict(os.environ)
    dotenv = ROOT / ".env"
    if dotenv.exists():
        for line in dotenv.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key and not key.startswith("#"):
                env.setdefault(key.strip(), value.strip().strip("\"'"))
    say(f"starting the engine on {SOURCE_RUN} (log: {LOG})")
    with open(LOG, "ab") as log:
        subprocess.Popen(
            [str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8040"],
            cwd=BACKEND, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True,
        )
    for _ in range(240):
        if answers(SOURCE_RUN):
            say("engine ready")
            return
        time.sleep(0.5)
    say(f"the engine did not answer within two minutes; see {LOG}")


def main() -> None:
    ensure_sdk()
    sys.path.insert(0, str(BACKEND))
    from app.agent_mcp import _engine, main as serve

    base = _engine()
    if not answers(base) and base == SOURCE_RUN and os.environ.get("FORMCUT_MCP_NO_START") != "1":
        start_engine()
    serve()


if __name__ == "__main__":
    main()
