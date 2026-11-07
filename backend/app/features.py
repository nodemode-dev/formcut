from fastapi import APIRouter

from .assets import router as assets
from .automation import router as automation
from .catalogue import router as catalogue
from .clip_visuals import router as clip_visuals
from .demo import router as demo
from .effect_previews import router as previews
from .extensions import router as extensions
from .fonts import router as fonts
from .jobs import router as jobs
from .local_speech import router as speech
from .model_manager import router as models
from .orchestration import router as orchestration
from .project_tracking import router as project_tracking
from .providers import router as providers_router
from .recovery import router as recovery
from .render_api import router as render
from .render_stream import router as playback
from .storage import router as storage
from .templates import router as templates

router = APIRouter()
for module in (
    assets,
    automation,
    catalogue,
    jobs,
    speech,
    models,
    render,
    templates,
    project_tracking,
    fonts,
    demo,
    previews,
    playback,
    clip_visuals,
    providers_router,
    storage,
    orchestration,
    recovery,
    extensions,
):
    router.include_router(module)
