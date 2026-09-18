import json
import threading
from pathlib import Path

from .paths import DATA_DIR
PROJECTS_FILE = DATA_DIR / "projects.json"
_lock = threading.Lock()


def _read() -> list[dict]:
    if not PROJECTS_FILE.exists():
        return []
    return json.loads(PROJECTS_FILE.read_text())


def _write(projects: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = PROJECTS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(projects, indent=2))
    temporary.replace(PROJECTS_FILE)


def list_projects() -> list[dict]:
    with _lock:
        return _read()


def get_project(project_id: str) -> dict | None:
    with _lock:
        return next((p for p in _read() if p["id"] == project_id), None)


def save_project(project: dict, expected_revision: int | None = None) -> dict:
    with _lock:
        projects = _read()
        current = next((p for p in projects if p["id"] == project["id"]), None)
        version = int(current.get("revision", 0)) if current else 0
        if expected_revision is not None and expected_revision != version:
            raise ValueError("Project changed; reload before saving")
        project["revision"] = version + 1
        projects = [p for p in projects if p["id"] != project["id"]]
        projects.append(project)
        _write(projects)
        return project


def delete_project(project_id: str) -> bool:
    with _lock:
        projects = _read()
        remaining = [p for p in projects if p["id"] != project_id]
        if len(remaining) == len(projects):
            return False
        _write(remaining)
        return True
