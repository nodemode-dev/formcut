# Engine map

Derived from the tree at v0.55.0, not from memory. Regenerate by listing
`backend/app` and reading each module's router prefix and decorators.

## Modules that serve routes

| Module | Lines | Prefix | Routes |
| --- | --- | --- | --- |
| assets.py | 122 | /api/assets | 3 |
| automation.py | 265 | /api/rpc | 2 |
| brush.py | 55 | /api/render | 1 |
| catalogue.py | 260 | /api/catalogue | 1 |
| clip_visuals.py | 131 | /api/media | 2 |
| demo.py | 59 | /api/demo | 2 |
| effect_previews.py | 96 | /api/catalogue/preview | 1 |
| export.py | 537 | /api/export | 3 |
| fonts.py | 49 | /api/assets | 1 |
| jobs.py | 96 | /api/jobs | 3 |
| local_speech.py | 92 | /api/speech | 2 |
| main.py | 60 | /api/health | 1 |
| media.py | 254 | /api/media | 8 |
| model_manager.py | 196 | /api/models | 4 |
| orchestration.py | 151 | /api/orchestration | 4 |
| presets.py | 121 | /api/presets | 5 |
| project_tracking.py | 63 | /api/track | 1 |
| projects.py | 58 | /api/projects | 5 |
| recovery.py | 74 | /api/recovery | 4 |
| providers.py | 150 | /api/providers | 4 |
| render_api.py | 142 | /api/render | 6 |
| render_stream.py | 71 | /api/render | 1 |
| stock.py | 259 | /api/stock | 5 |
| storage.py | 66 | /api/storage | 1 |
| templates.py | 164 | /api/templates | 7 |
| track.py | 96 | /api/track | 1 |
| tts.py | 91 | /api/tts | 3 |

## Modules with no routes of their own

These are the working parts the routed modules call: the renderer and its
helpers, the export graph, decoding, effects, expressions, paths, processes and
the automation transports.

- `audio_render.py` (108L)
- `cli.py` (54L)
- `expressions.py` (35L)
- `features.py` (29L)
- `fonts.py` (49L)
- `gpu.py` (78L)
- `main.py` (53L)
- `paths.py` (20L)
- `pixel_effects.py` (131L, clamps params to catalogue declarations)
- `processes.py` (22L)
- `project_tracking.py` (63L)
- `render_document.py` (83L)
- `renderer.py` (209L)
- `security.py` (42L)
- `segmentation.py` (53L)
- `store.py` (54L)
- `template_assets.py` (47L)
- `timing.py` (88L)
- `validation.py` (62L)
- `video_source.py` (141L)

## Reading order for a change

1. `main.py` for composition and the version constant.
2. `features.py` for what is mounted. One tuple, one include each.
3. The module owning the route you are changing, then `renderer.py` if it draws
   anything, `jobs.py` if it takes time, `paths.py` if it writes to disk.

## Data directory layout

Under `FORMCUT_DATA_DIR` or the platform default: `media/`, `projects/`,
`templates/`, `renders/`, `thumbs/`, `peaks/`, `filmstrips/`,
`catalogue-previews/`, `models/`, `ai-runtime/`, `recovery/`, `providers.json` (0600).
`GET /api/storage` measures these and marks which are rebuildable.
