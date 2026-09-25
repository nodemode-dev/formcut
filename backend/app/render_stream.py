import io
import math
import struct
import threading
import time

import anyio
import numpy as np
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from PIL import Image

from .render_api import _lock, _sessions
from .renderer import FrameRenderer

router = APIRouter(prefix="/api/render", tags=["render"])
HEADER = struct.Struct(">Id")
# size, time, width, height: sixteen bytes before each raw frame
RAW_HEADER = struct.Struct(">IdHH")


@router.get("/sessions/{session_id}/stream")
async def stream(request: Request, session_id: str, start: float = 0, fps: float = 30, format: str = "raw"):
    with _lock:
        item = _sessions.get(session_id)
        if not item:
            raise HTTPException(404, "Preview session expired")
        item["touched"] = time.monotonic()
        project, width = item["renderer"].project, item["renderer"].width
    if not math.isfinite(start) or start < 0 or not math.isfinite(fps) or not 1 <= fps <= 120:
        raise HTTPException(422, "Invalid playback request")
    rate = min(fps, float(project["fps"]))
    window = max(1, int(rate))
    began = time.monotonic()
    guard = threading.Lock()
    state = {"renderer": None, "index": -1, "closed": False}

    def produce():
        with guard:
            if state["closed"]:
                return None
            if state["renderer"] is None:
                state["renderer"] = FrameRenderer(project, width)
            previous = state["index"]
            index = max(previous + 1, min(int((time.monotonic() - began) * rate), previous + window))
            at = start + index / rate
            if at >= project["duration"]:
                return None
            wait = index / rate - (time.monotonic() - began)
            if wait > 0:
                time.sleep(wait)
            state["index"] = index
            pixels = state["renderer"].frame(at)
            if format == "jpeg":
                output = io.BytesIO()
                Image.fromarray(pixels).convert("RGB").save(output, format="JPEG", quality=82)
                data = output.getvalue()
                return HEADER.pack(len(data), at) + data
            # R4: the frame reaches the webview as the bytes the renderer made,
            # no encode here and no decode there; the header carries its size.
            data = np.ascontiguousarray(pixels[:, :, :4]).tobytes()
            return RAW_HEADER.pack(len(data), at, pixels.shape[1], pixels.shape[0]) + data

    def close():
        with guard:
            state["closed"] = True
            if state["renderer"] is not None:
                state["renderer"].close()

    async def body():
        try:
            while not await request.is_disconnected():
                chunk = await anyio.to_thread.run_sync(produce)
                if chunk is None:
                    return
                yield chunk
        finally:
            threading.Thread(target=close, daemon=True).start()

    return StreamingResponse(body(), media_type="application/octet-stream", headers={"Cache-Control": "no-store"})
