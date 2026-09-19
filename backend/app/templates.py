import copy
import json
import threading
import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .media import _find
from .paths import DATA_DIR
from .render_document import validate_document
from .timing import source_delta
from .template_assets import gather, restore

router = APIRouter(prefix="/api/templates", tags=["templates"])
ROOT = DATA_DIR / "templates"
_lock = threading.RLock()


def poster_frame(project: dict, at: float | None) -> str | None:
    """P4: a rendered frame stored with the template, for the poster gallery."""
    import base64 as _b64
    import io as _io

    from PIL import Image

    from .renderer import FrameRenderer
    try:
        renderer = FrameRenderer(project, 480)
    except Exception:
        return None
    try:
        moment = at if at is not None else min(1.0, float(project.get("duration", 1)) / 3)
        pixels = renderer.frame(max(0.0, moment))
        buffer = _io.BytesIO()
        Image.fromarray(pixels).convert("RGB").save(buffer, format="JPEG", quality=72)
        return _b64.b64encode(buffer.getvalue()).decode()
    except Exception:
        # A template must still save when its poster cannot be drawn.
        return None
    finally:
        renderer.close()


class TemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    poster_time: float | None = None
    project: dict
    media_ids: list[str] | None = None


class FillInput(BaseModel):
    bindings: dict[str, str]
    title: str = "Untitled from template"
    fit: bool = True


def get(template_id: str):
    if not template_id.isalnum():
        raise HTTPException(404, "Template not found")
    path = ROOT / (template_id + ".json")
    if not path.is_file():
        raise HTTPException(404, "Template not found")
    return json.loads(path.read_text())


def validate_template(item: dict) -> dict:
    if item.get("formcut_template") != 1 or not isinstance(item.get("slots"), list) or not str(item.get("name", "")).strip():
        raise ValueError("Invalid FormCut template")
    validate_document(item["project"])
    slot_ids = [s["id"] for s in item["slots"]]
    if len(set(slot_ids)) != len(slot_ids) or len(slot_ids) > 1000:
        raise ValueError("Template slots must be unique")
    for timeline in item["project"]["timelines"]:
        for track in timeline["tracks"]:
            for clip in track["clips"]:
                if clip.get("templateSlot") and clip["templateSlot"] not in slot_ids:
                    raise ValueError("Unknown template slot")
    return item


@router.get("")
def list_templates():
    if not ROOT.exists():
        return []
    with _lock:
        return [{k: item[k] for k in ("id", "name", "slots")} for path in ROOT.glob("*.json") for item in [json.loads(path.read_text())]]


@router.post("", status_code=201)
def create(body: TemplateInput):
    try:
        project = validate_document(body.project)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    slots = {}
    for timeline in project["timelines"]:
        for track in timeline["tracks"]:
            for clip in track["clips"]:
                media_id = clip.get("mediaId")
                if not media_id or (body.media_ids is not None and media_id not in body.media_ids):
                    continue
                if media_id not in slots:
                    slots[media_id] = {"id": uuid.uuid4().hex, "name": clip.get("label", "Media"), "kind": clip["kind"]}
                clip["templateSlot"] = slots[media_id]["id"]
                clip.pop("mediaId", None)
    item = {"formcut_template": 1, "id": uuid.uuid4().hex, "name": body.name, "project": project, "slots": list(slots.values())}
    item["assets"] = gather(project)
    # The poster is drawn from the project as it arrived: by this point the slot
    # clips have had their media removed, so rendering `project` would draw a
    # hole where the person's footage goes.
    item["poster"] = poster_frame(body.project, body.poster_time)
    ROOT.mkdir(parents=True, exist_ok=True)
    with _lock:
        (ROOT / (item["id"] + ".json")).write_text(json.dumps(item))
    return item


@router.get("/{template_id}")
def read(template_id: str):
    return get(template_id)


@router.post("/{template_id}/fill")
def fill(template_id: str, body: FillInput):
    item = get(template_id)
    project = copy.deepcopy(item["project"])
    media = {}
    for slot in item["slots"]:
        if slot["id"] not in body.bindings:
            raise HTTPException(422, "Fill every media slot")
        record = _find(body.bindings[slot["id"]])
        if record["kind"] != slot["kind"]:
            raise HTTPException(422, f"Slot {slot['name']} needs {slot['kind']}")
        media[slot["id"]] = record
    for timeline in project["timelines"]:
        timeline["id"] = uuid.uuid4().hex
        for track in timeline["tracks"]:
            track["id"] = uuid.uuid4().hex
            for clip in track["clips"]:
                clip["id"] = uuid.uuid4().hex
                slot_id = clip.pop("templateSlot", None)
                if slot_id:
                    record = media[slot_id]
                    clip["mediaId"] = record["id"]
                    clip["label"] = record["name"]
                    if clip["kind"] != "image" and body.fit:
                        clip["sourceIn"] = 0
                        span = source_delta(clip, clip["duration"])
                        ratio = record["duration"] / max(1e-9, span)
                        if clip.get("speedCurve"):
                            for point in clip["speedCurve"]:
                                point["speed"] *= ratio
                                if not 0.05 <= point["speed"] <= 16:
                                    raise HTTPException(422, "Replacement duration requires an unsupported speed")
                        else:
                            clip["speed"] = float(clip.get("speed", 1)) * ratio
                            if not 0.05 <= clip["speed"] <= 16:
                                raise HTTPException(422, "Replacement duration requires an unsupported speed")
    project.update(title=body.title, projectId=None, saved=False, playing=False, playhead=0, selectedClipId=None)
    return project


@router.get("/{template_id}/file")
def export(template_id: str):
    return Response(json.dumps(get(template_id), indent=2), media_type="application/json", headers={"Content-Disposition": 'attachment; filename="template.fctemplate"'})


@router.post("/import", status_code=201)
def import_template(file: UploadFile):
    raw = file.file.read(32_000_001)
    if len(raw) > 32_000_000:
        raise HTTPException(413, "Template exceeds 32 MB")
    try:
        item = validate_template(json.loads(raw))
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        restore(item)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    item["id"] = uuid.uuid4().hex
    ROOT.mkdir(parents=True, exist_ok=True)
    with _lock:
        (ROOT / (item["id"] + ".json")).write_text(json.dumps(item))
    return item


@router.delete("/{template_id}", status_code=204)
def delete(template_id: str):
    get(template_id)
    with _lock:
        (ROOT / (template_id + ".json")).unlink()
