"""Recovery journal: the last unsaved document per project, written by the interface as edits happen.

Lives under DATA_DIR/recovery as one JSON file per key; the key is the project id or "unsaved" for a project that
has never been saved. Mutating calls require the local header like every other write.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .paths import DATA_DIR

router = APIRouter(prefix="/api/recovery", tags=["recovery"])
RECOVERY_DIR = DATA_DIR / "recovery"
_KEY = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _path(key: str):
    if not _KEY.match(key):
        raise HTTPException(status_code=400, detail="bad key")
    return RECOVERY_DIR / f"{key}.json"


class JournalBody(BaseModel):
    key: str
    revision: int = 0
    document: dict[str, Any]


@router.get("")
def list_journals() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not RECOVERY_DIR.is_dir():
        return out
    for file in sorted(RECOVERY_DIR.glob("*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"key": file.stem, "written": data.get("written"), "revision": data.get("revision", 0), "title": (data.get("document") or {}).get("title", "")})
    return out


@router.get("/{key}")
def read_journal(key: str) -> dict[str, Any]:
    path = _path(key)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="no journal")
    return json.loads(path.read_text(encoding="utf-8"))


@router.put("")
def write_journal(body: JournalBody) -> dict[str, Any]:
    RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
    path = _path(body.key)
    record = {"written": time.time(), "revision": body.revision, "document": body.document}
    # Each write gets its own temporary name. With one shared name, two journal
    # writes landing together raced: the first replace consumed the file the
    # second was about to move, and that one failed with a missing temp file.
    tmp = path.with_name(f"{path.stem}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(record), encoding="utf-8")
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return {"key": body.key, "written": record["written"]}


@router.delete("/{key}")
def clear_journal(key: str) -> dict[str, bool]:
    path = _path(key)
    existed = path.is_file()
    if existed:
        path.unlink()
    return {"cleared": existed}
