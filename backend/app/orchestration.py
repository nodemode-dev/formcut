"""Orchestration: who is driving this engine, what they did, and a live feed.

The automation surface already lets an external system build, edit and render a
project. What it could not do is say who was driving, let the person in front of
the app see it happen, or tell the outside world when something finished without
polling. That is what this module adds, and it is deliberately transport
agnostic: an orchestrator registers a session, calls the existing JSON-RPC
methods with its session id, and subscribes to an event stream. Nothing here
assumes a particular orchestrator, protocol or direction of connection.

Events are broadcast in process to every subscriber, newest first for late
joiners through a short backlog, so a graph that connects mid-render still sees
the job it cares about rather than nothing until the next tick.
"""

import asyncio
import json
import threading
import time
import uuid
from collections import deque

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])

BACKLOG = 50
OPERATIONS = 20

_lock = threading.RLock()
_sessions: dict[str, dict] = {}
_backlog: deque = deque(maxlen=BACKLOG)
_subscribers: set[asyncio.Queue] = set()
_loop: asyncio.AbstractEventLoop | None = None


class SessionInput(BaseModel):
    name: str
    agent: str | None = None


def remember_loop(loop: asyncio.AbstractEventLoop) -> None:
    """The event loop that owns the subscriber queues.

    Jobs run on worker threads, so publishing has to hop back to the loop; this
    is captured once at startup rather than guessed per call.
    """
    global _loop
    _loop = loop


def publish(kind: str, **fields) -> None:
    """Broadcast an event. Safe from any thread, and never raises into a job."""
    event = {"kind": kind, "at": round(time.time(), 3), **fields}
    with _lock:
        _backlog.append(event)
        targets = list(_subscribers)
    if not targets:
        return
    loop = _loop
    for queue in targets:
        try:
            if loop and loop.is_running():
                loop.call_soon_threadsafe(queue.put_nowait, event)
            else:
                queue.put_nowait(event)
        except (RuntimeError, asyncio.QueueFull):
            # A subscriber that cannot keep up is dropped by its own reader; a
            # publisher must never fail because of one slow listener.
            continue


def note_operation(session_id: str | None, method: str, detail: dict | None = None) -> None:
    """Record an orchestrated call against its session, and announce it."""
    if session_id:
        with _lock:
            session = _sessions.get(session_id)
            if session is not None:
                session["operations"].append({"method": method, "at": round(time.time(), 3), **(detail or {})})
                session["operations"] = session["operations"][-OPERATIONS:]
                session["last"] = round(time.time(), 3)
    publish("operation", session=session_id, method=method, **(detail or {}))


@router.post("/sessions", status_code=201)
def open_session(body: SessionInput) -> dict:
    session = {
        "id": uuid.uuid4().hex,
        "name": body.name.strip()[:80] or "orchestrator",
        "agent": (body.agent or "").strip()[:120],
        "started": round(time.time(), 3),
        "last": round(time.time(), 3),
        "operations": [],
    }
    with _lock:
        _sessions[session["id"]] = session
    publish("session.open", session=session["id"], name=session["name"])
    return session


@router.get("/sessions")
def list_sessions() -> list[dict]:
    with _lock:
        return sorted(_sessions.values(), key=lambda entry: -entry["last"])


@router.delete("/sessions/{session_id}", status_code=204)
def close_session(session_id: str) -> None:
    with _lock:
        session = _sessions.pop(session_id, None)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    publish("session.close", session=session_id, name=session["name"])


@router.get("/events")
async def events(request: Request, since: float = 0.0) -> StreamingResponse:
    """Server-sent events: sessions, operations and job progress.

    Plain SSE rather than a websocket, because the feed is one directional and
    every orchestrator, browser and shell script can read it without a library.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=200)
    with _lock:
        history = [event for event in _backlog if event["at"] > since]
        _subscribers.add(queue)

    async def body():
        try:
            for event in history:
                yield f"data: {json.dumps(event)}\n\n"
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except asyncio.TimeoutError:
                    # A comment keeps the connection warm through proxies and
                    # tells a reader the stream is alive rather than stalled.
                    yield ": keepalive\n\n"
                    continue
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            with _lock:
                _subscribers.discard(queue)

    return StreamingResponse(body(), media_type="text/event-stream",
                             headers={"cache-control": "no-store", "x-accel-buffering": "no"})


def session_from_header(value: str | None = Header(default=None, alias="x-formcut-session")) -> str | None:
    return value
