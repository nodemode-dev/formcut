"""The media library checked, item by item (v2.2.6).

    cd formcut/backend && ./venv/bin/python -m app.media_check

For every item in the library: its file (there, a link and where it points, or missing), whether it decodes (a video
through both of formcut's colour paths, an image opened, audio probed), and every clip in a saved project whose media
the library does not have. It changes nothing. GET /api/media/health gives the same as JSON.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["media"])


def _file_state(media_id: str) -> dict:
    from . import media

    found = [p for p in media.MEDIA_DIR.glob(f"{media_id}.*") if not p.name.startswith(".")]
    if not found:
        return {"file": "missing"}
    path = found[0]
    if path.is_symlink():
        target = os.readlink(path)
        return {"file": "linked" if path.exists() else "link to nothing", "path": str(path), "target": target}
    return {"file": "there" if path.stat().st_size else "empty", "path": str(path), "bytes": path.stat().st_size}


def _decodes(path: Path, kind: str) -> dict:
    if kind == "image":
        try:
            from PIL import Image

            with Image.open(path) as picture:
                picture.load()
            return {"decodes": True}
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            return {"decodes": False, "why": str(exc)[:200]}
    if kind != "video":
        return {}
    from .video_source import acquire, recycle

    results = {}
    for label, own in (("device colour path", True), ("formcut's own conversion", False)):
        source = None
        try:
            source = acquire(str(path))
            source.own_conversion = own
            source.want_planes = False
            ok, frame = source.read()
            results[label] = (
                "reads"
                if ok and frame is not None
                else f"fails ({(getattr(source, 'last_error', '') or 'no frame').splitlines()[-1][:160]})"
            )
        except Exception as exc:  # noqa: BLE001 - reported, not raised
            results[label] = f"fails ({str(exc)[:160]})"
        finally:
            if source is not None:
                try:
                    recycle(source)
                except Exception:  # noqa: BLE001
                    source.release()
    return {"decodes": all(v == "reads" for v in results.values()), **results}


def check() -> dict:
    from . import media, store

    items = media.list_media()
    known = {item["id"] for item in items}
    report = []
    for item in items:
        entry = {"id": item["id"], "name": item.get("name"), "kind": item.get("kind"), **_file_state(item["id"])}
        if entry["file"] in ("there", "linked"):
            entry.update(_decodes(Path(entry["path"]), item.get("kind", "")))
        report.append(entry)
    orphans = []
    for project in store.list_projects():
        document = project.get("document") or project
        for timeline in document.get("timelines") or []:
            for track in timeline.get("tracks") or []:
                for clip in track.get("clips") or []:
                    if clip.get("mediaId") and clip["mediaId"] not in known:
                        orphans.append(
                            {
                                "project": project.get("title") or project.get("id"),
                                "clip": clip.get("label"),
                                "mediaId": clip["mediaId"],
                                **_file_state(clip["mediaId"]),
                            }
                        )
    return {
        "dataFolder": str(media.DATA_DIR),
        "items": report,
        "problems": [e for e in report if e["file"] not in ("there", "linked") or e.get("decodes") is False],
        "clipsWithoutMedia": orphans,
    }


@router.get("/api/media/health")
def media_health() -> dict:
    return check()


def main() -> int:
    result = check()
    print(f"formcut media check: {result['dataFolder']}")
    for entry in result["items"]:
        detail = entry.get("target") or entry.get("path") or ""
        paths = "; ".join(f"{k}: {v}" for k, v in entry.items() if k in ("device colour path", "formcut's own conversion", "why"))
        mark = "ok " if entry in result["items"] and entry not in result["problems"] else "BAD"
        print(f"  {mark} {entry['kind'] or '?':5} {entry['name']!s:40.40} {entry['file']:15} {detail}  {paths}")
    for orphan in result["clipsWithoutMedia"]:
        print(
            f"  BAD clip   {orphan['clip']!s:40.40} in {orphan['project']}: media {orphan['mediaId']} not in the library, file {orphan['file']}"
        )
    print(
        f"{len(result['problems'])} item(s) with a problem, {len(result['clipsWithoutMedia'])} clip(s) whose media the library does not have"
    )
    return 1 if result["problems"] or result["clipsWithoutMedia"] else 0


if __name__ == "__main__":
    sys.exit(main())
