import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import store

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
