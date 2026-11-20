"""The window key: a per-launch secret that only the formcut window holds.

The engine makes it at start and keeps it in memory. The desktop shell starts
the engine with FORMCUT_WINDOW_KEY_STDOUT=1 and reads one line,
`formcut-window-key: <key>`, printed before the address; it hands the key to
the window it opens. Run from source (no shell), the window asks for it once at
POST /api/window/key, which answers one time per launch and refuses after.
Every write needs the key (security.LocalOnly checks it), and a socket the
window opens carries a one-time ticket bought with it.
"""

from __future__ import annotations

import hmac
import os
import secrets
import time

from fastapi import APIRouter, HTTPException, Request

HEADER = "x-formcut-window-key"
STDOUT_ENV = "FORMCUT_WINDOW_KEY_STDOUT"
LINE = "formcut-window-key: "
REFUSED = "Only the formcut window can do this"
TICKET_LIFE = 30.0
KEY = secrets.token_urlsafe(32)
STATE = {"claimed": False, "secondClaim": False}
TICKETS: dict[str, float] = {}

router = APIRouter(prefix="/api/window", tags=["window"])


def stdout_mode() -> bool:
    return os.environ.get(STDOUT_ENV) == "1"


def valid(value) -> bool:
    return isinstance(value, str) and bool(value) and hmac.compare_digest(value.encode("utf-8"), KEY.encode("utf-8"))


def require(request: Request) -> None:
    if not valid(request.headers.get(HEADER)):
        raise HTTPException(403, REFUSED)


def ticket() -> str:
    now = time.monotonic()
    for old in [t for t, at in TICKETS.items() if now - at > TICKET_LIFE]:
        TICKETS.pop(old, None)
    value = secrets.token_urlsafe(24)
    TICKETS[value] = now
    return value


def spend(value) -> bool:
    if not isinstance(value, str) or not value:
        return False
    at = TICKETS.pop(value, None)
    return at is not None and time.monotonic() - at <= TICKET_LIFE


@router.post("/key")
def claim(request: Request) -> dict:
    if stdout_mode() or request.scope.get("formcut.remote"):
        raise HTTPException(404, "Not Found")
    if STATE["claimed"]:
        STATE["secondClaim"] = True
        raise HTTPException(409, "The window key was already given to a window in this launch")
    STATE["claimed"] = True
    return {"key": KEY}


@router.post("/ticket")
def socket_ticket(request: Request) -> dict:
    require(request)
    return {"ticket": ticket()}


@router.get("/state")
def state() -> dict:
    return {"packaged": stdout_mode(), "secondClaim": STATE["secondClaim"]}
