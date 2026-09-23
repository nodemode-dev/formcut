"""Where agents find the formcut that is running.

The desktop app starts its engine on a port the operating system chooses, and
only the app's own window knew it, so an agent could drive formcut only when it
was run from the repository. The engine now publishes its address in engine.json
in formcut's data folder while it runs, and the MCP server (agent_mcp.py) reads
it on every call. A file left behind by an engine that was killed is ignored,
because the address must also answer as formcut.
"""

from __future__ import annotations

import atexit
import datetime
import json
import os

from .paths import DATA_DIR

RECORD = DATA_DIR / "engine.json"


def publish(url: str, version: str) -> None:
    """Record this engine's address, and withdraw it when this process ends."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "url": url,
        "pid": os.getpid(),
        "version": version,
        "started": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
    }
    staged = RECORD.with_suffix(".json.tmp")
    staged.write_text(json.dumps(record), encoding="utf-8")
    os.replace(staged, RECORD)
    atexit.register(withdraw)


def withdraw() -> None:
    """Remove the record, if it is still this process's (a newer engine may have replaced it)."""
    try:
        if json.loads(RECORD.read_text(encoding="utf-8")).get("pid") == os.getpid():
            RECORD.unlink()
    except (OSError, ValueError):
        pass


def running_engine(timeout: float = 1.0) -> str | None:
    """The published address, if a formcut engine answers there; None otherwise.

    Liveness is asked of the engine itself rather than of the process: os.kill(pid, 0)
    would terminate the process on Windows.
    """
    try:
        url = json.loads(RECORD.read_text(encoding="utf-8")).get("url")
    except (OSError, ValueError):
        return None
    if not isinstance(url, str) or not url.startswith("http://127.0.0.1:"):
        return None
    import httpx

    try:
        response = httpx.get(f"{url}/api/health", timeout=timeout, headers={"x-formcut-local": "1"})
        return url if response.status_code == 200 and response.json().get("status") == "ok" else None
    except (httpx.HTTPError, ValueError):
        return None
