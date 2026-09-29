import contextlib
import json
import threading
import time

from .durable import read_json, set_aside, write_json
from .paths import DATA_DIR

PROJECTS_FILE = DATA_DIR / "projects.json"
# Every project also as a file of its own (v2.2.3): projects.json held them all, and a damaged one failed every
# project. It is now durable (durable.py: written whole, the previous version kept, a damaged file set aside and its
# backup read), and when it and its backup are both gone it is rebuilt from these.
RECORDS_DIR = DATA_DIR / "project-records"
_lock = threading.Lock()
_record_texts: dict[str, str] = {}


def _read() -> list[dict]:
    """projects.json; when it is missing or damaged, the projects' own records (the latest word on each, a deleted
    project's gone with it), else its backup (one save behind), else none."""
    try:
        projects = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        if isinstance(projects, list):
            return projects
        raise ValueError("not a list of projects")
    except FileNotFoundError:
        pass
    except (OSError, ValueError) as exc:
        set_aside(PROJECTS_FILE, exc)
    rebuilt = []
    for path in sorted(RECORDS_DIR.glob("*.json")) if RECORDS_DIR.is_dir() else []:
        with contextlib.suppress(OSError, ValueError):
            project = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(project, dict) and project.get("id"):
                rebuilt.append(project)
    if rebuilt:
        write_json(PROJECTS_FILE, rebuilt, keep_backup=False)
        return rebuilt
    return read_json(PROJECTS_FILE, [])


def _write(projects: list[dict]) -> None:
    write_json(PROJECTS_FILE, projects)
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    for project in projects:
        project_id = str(project.get("id") or "")
        if not project_id or "/" in project_id or "\\" in project_id or project_id.startswith("."):
            continue
        text = json.dumps(project)
        if _record_texts.get(project_id) != text:
            write_json(RECORDS_DIR / f"{project_id}.json", project, indent=None, keep_backup=False)
            _record_texts[project_id] = text


def list_projects() -> list[dict]:
    with _lock:
        return _read()


def get_project(project_id: str) -> dict | None:
    with _lock:
        return next((p for p in _read() if p["id"] == project_id), None)


def save_project(project: dict, expected_revision: int | None = None) -> dict:
    saved = _save_project(project, expected_revision)
    # Opt-in sync: the package follows the save into the project's own sync folder, when it names one.
    document = saved.get("document") or saved
    if document.get("syncFolder"):
        from .project_packages import sync_after_save

        # a folder that vanished or a full disk does not fail the save; the next save tries again
        with contextlib.suppress(OSError):
            sync_after_save(saved)
    # a project kept in a .fmc file: the file follows the save (project_files.py)
    from .project_files import after_save

    after_save(saved)
    return saved


def _save_project(project: dict, expected_revision: int | None = None) -> dict:
    # When it was last written, so the home screen can say more than a title.
    project = {**project, "updated": time.time()}
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
        (RECORDS_DIR / f"{project_id}.json").unlink(missing_ok=True)  # deleted: not to be rebuilt
        _record_texts.pop(project_id, None)
        return True
