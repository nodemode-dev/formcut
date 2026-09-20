import uuid

from fastapi.responses import FileResponse
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import store
from .paths import DATA_DIR

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectIn(BaseModel):
    title: str = "Untitled project"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    timelines: list[dict] = []
    activeTimeline: int = 0
    revision: int = 0


class Project(ProjectIn):
    id: str


COVERS = DATA_DIR / "covers"


def _summary(record: dict) -> dict:
    """What the home screen needs to tell one project from another.

    A title alone is not enough once there are more than three: when it was last
    touched, how long it runs, how much is in it, and a picture of it.
    """
    document = record.get("document") or record
    timelines = document.get("timelines") or []
    clips = sum(len(track.get("clips") or []) for timeline in timelines for track in timeline.get("tracks") or [])
    duration = 0.0
    for timeline in timelines:
        for track in timeline.get("tracks") or []:
            for clip in track.get("clips") or []:
                duration = max(duration, float(clip.get("start", 0)) + float(clip.get("duration", 0)))
    path = COVERS / f"{record.get('id')}.jpg"
    # The store keeps no timestamp, so the file's own is the honest answer
    # rather than showing every project as never opened.
    stamp = float(record.get("updated") or record.get("saved") or 0)
    return {
        "id": record.get("id"), "title": record.get("title") or "",
        "updated": stamp,
        "clips": clips, "duration": round(duration, 2),
        "timelines": len(timelines),
        "width": document.get("width"), "height": document.get("height"),
        "cover": path.is_file(),
    }


@router.get("/summaries")
def project_summaries() -> list[dict]:
    items = [_summary(p) for p in store.list_projects()]
    return sorted(items, key=lambda entry: entry["updated"], reverse=True)


@router.get("/{project_id}/cover")
def project_cover(project_id: str):
    path = COVERS / f"{project_id}.jpg"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="no cover")
    return FileResponse(path, media_type="image/jpeg")


@router.put("/{project_id}/cover", status_code=204)
def set_project_cover(project_id: str, body: dict) -> None:
    """Render the frame at a given moment and keep it as the project's picture."""
    from .render_api import FrameRenderer
    from .render_document import validate_document
    from PIL import Image
    document = validate_document(body.get("project") or {})
    COVERS.mkdir(parents=True, exist_ok=True)
    renderer = FrameRenderer(document, 480)
    try:
        pixels = renderer.frame(max(0.0, float(body.get("time") or 0)))
    finally:
        renderer.close()
    Image.fromarray(pixels[:, :, :3]).save(COVERS / f"{project_id}.jpg", quality=80)


@router.patch("/{project_id}", status_code=200)
def rename_project(project_id: str, body: dict) -> Project:
    found = store.get_project(project_id)
    if found is None:
        raise HTTPException(status_code=404, detail="project not found")
    title = str(body.get("title") or "").strip()[:120]
    if not title:
        raise HTTPException(status_code=422, detail="a project needs a name")
    found["title"] = title
    return Project(**store.save_project(found))


@router.get("")
def list_projects() -> list[Project]:
    return [Project(**p) for p in store.list_projects()]


@router.post("", status_code=201)
def create_project(body: ProjectIn) -> Project:
    project = Project(id=uuid.uuid4().hex, **body.model_dump())
    return Project(**store.save_project(project.model_dump()))


@router.get("/{project_id}")
def get_project(project_id: str) -> Project:
    found = store.get_project(project_id)
    if found is None:
        raise HTTPException(status_code=404, detail="project not found")
    return Project(**found)


@router.put("/{project_id}")
def update_project(project_id: str, body: ProjectIn) -> Project:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    project = Project(id=project_id, **body.model_dump())
    try:
        return Project(**store.save_project(project.model_dump(), expected_revision=body.revision))
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str):
    if not store.delete_project(project_id):
        raise HTTPException(status_code=404, detail="project not found")
