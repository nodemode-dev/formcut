"""Outside agents: what they may do, and the window's answer when they ask.

An outside agent (the MCP server, the command line, any local program) asks
POST /api/agent-access/request before a tool that changes something. The
stored choice decides: blocked refuses, allowed gives a pass at once, ask puts
the request in front of the window (Deny, Allow once, Always allow) and waits
up to two minutes, refusing at once when no window is open. A pass is sent as
the x-formcut-agent-pass header on the writes of that one tool call; it never
opens a terminal, answers a prompt or changes the choice, which take the
window key. The Agent terminal's shell carries its own tab token in its
environment; a request with a live tab token gets a pass without a question,
except under blocked, which refuses every agent, formcut's own tabs included.

The choice lives in agent-access.json in formcut's data folder, sealed with a
key in the system keychain (seal.py). A choice edited outside the app reads as
ask, and the window says so; without a keychain the engine starts, reports the
seal as unavailable, and a stored allowed is not honoured.
"""

from __future__ import annotations

import hmac
import secrets
import threading
import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from . import seal, window_key
from .durable import read_json, write_json
from .paths import DATA_DIR

router = APIRouter(prefix="/api/agent-access", tags=["agent-access"])

STORE = DATA_DIR / "agent-access.json"
CHOICES = ("ask", "allowed", "blocked")
PASS_HEADER = "x-formcut-agent-pass"
TAB_HEADER = "x-formcut-agent-tab"
TAB_ENV = "FORMCUT_AGENT_TAB"
PASS_LIFE = 900.0
ASK_SECONDS = 120.0
BROKEN = "Outside agent access was changed outside formcut, so it is back to Ask."
NO_WINDOW = "formcut asks before an outside agent changes anything, and no formcut window is open: open formcut, or choose Allowed in Settings"
_lock = threading.Lock()
_passes: dict[str, float] = {}
_tabs: set[str] = set()
EVENTS_KEPT = 200
_news = threading.Condition()
_events: list[dict] = []
_seq = {"last": 0}


def _withdraw(rid: str, reason: str) -> None:
    """Every window learns that a question is over: answered, expired, or never shown."""
    with _news:
        _seq["last"] += 1
        _events.append({"seq": _seq["last"], "type": "withdrawn", "id": rid, "reason": reason, "at": int(time.time() * 1000)})
        del _events[:-EVENTS_KEPT]
        _news.notify_all()


def _consent(tool: str, agent: str, client: str, notice: str) -> dict:
    """The question as the window gets it; tool, agent and notice are what the page has always read."""
    return {
        "tool": tool,
        "agent": agent,
        "notice": notice,
        "client": client,
        "what": f"run {tool}",
        "offers": ["deny", "once", "always"] if seal.available() else ["deny", "once"],
        "always": "all",
        "expires": int((time.time() + ASK_SECONDS) * 1000),
        "escape": "deny",
        "notes": [notice] if notice else [],
    }


def _stored() -> dict:
    data = read_json(STORE, {})
    return data if isinstance(data, dict) else {}


def state() -> dict:
    """The choice as it stands, with the seal's verdict."""
    stored = _stored()
    values = {"outsideAgents": stored.get("outsideAgents") if stored.get("outsideAgents") in CHOICES else "ask"}
    if "seal" in stored:
        values["seal"] = stored["seal"]
    found = seal.effective(values)
    choice = found["outsideAgents"]
    if found["seal"] == "unavailable" and choice == "allowed":
        choice = "ask"
    return {
        "choice": choice,
        "stored": values["outsideAgents"],
        "seal": found["seal"],
        "sealBroken": found["sealBroken"],
        "notice": BROKEN if found["sealBroken"] else "",
    }


def _store(choice: str) -> dict:
    signed = seal.sign({"outsideAgents": choice})
    write_json(STORE, signed, private=True)
    return state()


def _grant() -> str:
    value = secrets.token_urlsafe(24)
    now = time.monotonic()
    with _lock:
        for old in [p for p, at in _passes.items() if now - at > PASS_LIFE]:
            _passes.pop(old, None)
        _passes[value] = now
    return value


def pass_valid(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    with _lock:
        at = next((v for k, v in _passes.items() if hmac.compare_digest(k.encode(), value.encode())), None)
    return at is not None and time.monotonic() - at <= PASS_LIFE


def release(value: str) -> None:
    with _lock:
        _passes.pop(value, None)


def open_tab() -> str:
    """A token for one Agent terminal tab, live until close_tab."""
    value = secrets.token_urlsafe(24)
    with _lock:
        _tabs.add(value)
    return value


def close_tab(value: str) -> None:
    with _lock:
        _tabs.discard(value)


def tab_live(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    with _lock:
        return any(hmac.compare_digest(t.encode(), value.encode()) for t in _tabs)


def decide(tool: str, agent: str, tab: str | None = None, client: str = "") -> str:
    """A pass for one tool call, or ValueError with the sentence to show the agent."""
    current = state()
    if current["choice"] == "blocked":
        raise ValueError("Outside agents are blocked in formcut's Settings, so nothing was changed")
    if tab_live(tab) or current["choice"] == "allowed":
        return _grant()
    from .extensions import ENDED, WindowAbsentError, ask_window

    ENDED["consent"] = _withdraw

    try:
        answer = ask_window("consent", _consent(tool, agent, client, current["notice"]), ASK_SECONDS)
    except WindowAbsentError as exc:
        if "did not answer" in str(exc):
            raise ValueError(f"Nobody answered in the formcut window within {ASK_SECONDS:.0f} s, so nothing was changed") from exc
        raise ValueError(NO_WINDOW) from exc
    result = answer.get("result")
    if result == "always" and seal.available():
        _store("allowed")
    if result in ("always", "once"):
        return _grant()
    raise ValueError("The person said no in the formcut window, so nothing was changed")


class Choice(BaseModel):
    choice: str


class AgentRequest(BaseModel):
    tool: str = ""
    agent: str = ""
    client: str = ""


@router.get("")
def read_choice() -> dict:
    return state()


@router.put("")
def set_choice(body: Choice, request: Request) -> dict:
    window_key.require(request)
    if body.choice not in CHOICES:
        raise HTTPException(422, f"choice must be one of {', '.join(CHOICES)}")
    if body.choice == "allowed" and not seal.available():
        raise HTTPException(409, "Allowed cannot be kept without the system keychain; formcut will ask each time")
    return _store(body.choice)


@router.post("/request")
def request_pass(body: AgentRequest, request: Request) -> dict:
    if request.scope.get("formcut.remote"):
        raise HTTPException(403, "Outside agents are served on this computer only")
    try:
        value = decide(
            body.tool[:120] or "a tool", body.agent[:120] or "an outside agent", request.headers.get(TAB_HEADER), body.client[:120]
        )
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from exc
    return {"pass": value, "header": PASS_HEADER, "seconds": PASS_LIFE}


@router.get("/waiting")
def waiting_requests(request: Request) -> dict:
    if request.scope.get("formcut.remote"):
        raise HTTPException(403, "Outside agents are answered on this computer only")
    from .extensions import waiting

    with _news:
        seq = _seq["last"]
    return {"seq": seq, "requests": waiting("consent")}


@router.get("/events")
def events(request: Request, after: int = -1, wait: float = 25.0) -> dict:
    if request.scope.get("formcut.remote"):
        raise HTTPException(403, "Outside agents are answered on this computer only")
    deadline = time.monotonic() + max(0.0, min(wait, 30.0))
    with _news:
        while after >= 0 and _seq["last"] <= after:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            _news.wait(left)
        return {"seq": _seq["last"], "events": [dict(e) for e in _events if after >= 0 and e["seq"] > after]}


@router.delete("/pass")
def end_pass(request: Request) -> dict:
    value = request.headers.get(PASS_HEADER, "")
    release(value)
    return {"ok": True}
