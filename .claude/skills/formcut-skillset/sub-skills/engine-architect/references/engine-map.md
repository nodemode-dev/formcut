# Engine map

The two module sections are generated from `backend/app` by
`python setup/skill_maps.py`; run it after adding, removing or renaming a module.
The rest is written by hand.

## Contents

- Modules that serve routes
- Modules with no routes of their own
- Reading order for a change
- Data directory layout
- v0.56.0 delta
- v0.57.0 delta
- v0.58.0 delta
- v0.59.0 delta
- v0.60.0 delta
- v0.61.0 delta

## Modules that serve routes

| Module | Lines | Prefix | Routes |
| --- | --- | --- | --- |
| addons.py | 194 | /api/addons | 3 |
| agent_connect.py | 145 | /api/agents | 2 |
| assets.py | 135 | /api/assets | 3 |
| automation.py | 711 | /api/rpc | 2 |
| brush.py | 106 | /api/render | 2 |
| catalogue.py | 863 | /api/catalogue | 1 |
| clip_visuals.py | 165 | /api/media | 2 |
| cloud.py | 447 | /api/cloud | 9 |
| codecs_api.py | 45 | /api/codecs | 4 |
| demo.py | 59 | /api/demo | 2 |
| effect_previews.py | 269 | /api/catalogue/preview | 1 |
| fonts.py | 93 | /api/assets | 1 |
| generate.py | 308 | /api/generate | 2 |
| instagram.py | 213 | /api/connect/instagram | 4 |
| jobs.py | 104 | /api/jobs | 3 |
| library.py | 2506 | /api/library | 5 |
| local_speech.py | 425 | /api/speech | 4 |
| main.py | 410 | /api/health | 13 |
| media.py | 864 | /api/media | 25 |
| model_manager.py | 528 | /api/models | 8 |
| orchestration.py | 150 | /api/orchestration | 4 |
| presets.py | 465 | /api/presets | 8 |
| project_packages.py | 312 | /api/projects | 4 |
| project_tracking.py | 89 | /api/track | 1 |
| projects.py | 175 | /api/projects | 9 |
| providers.py | 161 | /api/providers | 4 |
| recovery.py | 89 | /api/recovery | 4 |
| remote.py | 264 | /api/remote | 6 |
| render_api.py | 1069 | /api/render | 13 |
| render_stream.py | 80 | /api/render | 1 |
| stock.py | 422 | /api/stock | 7 |
| storage.py | 66 | /api/storage | 1 |
| subtitles.py | 109 | /api/subtitles | 2 |
| templates.py | 214 | /api/templates | 7 |
| terminal.py | 181 | /api/terminal | 2 |
| tiktok.py | 340 | /api/connect/tiktok/app | 7 |
| track.py | 178 | /api/track | 1 |
| transcribe.py | 525 | /api/transcribe | 2 |
| tts.py | 91 | /api/tts | 3 |
| upscale.py | 313 | /api/media | 2 |
| webhooks.py | 252 | /api/webhooks | 5 |

## Modules with no routes of their own

These are the working parts the routed modules call: the renderer and its
helpers, the export graph, decoding, effects, expressions, paths, processes and
the automation transports.

- `agent_mcp.py` (739L)
- `ai_upscale.py` (131L)
- `audio_render.py` (231L)
- `bench.py` (476L)
- `cli.py` (61L)
- `color_grade.py` (239L)
- `discovery.py` (65L)
- `effect_packages.py` (433L)
- `encoders.py` (297L)
- `expressions.py` (51L)
- `fast_export.py` (301L)
- `fast_layers.py` (408L)
- `features.py` (43L)
- `ffmpeg_fetch.py` (165L)
- `frame_cache.py` (146L)
- `gif_export.py` (78L)
- `gpu.py` (701L)
- `gpu_effects.py` (2744L)
- `gpu_frame.py` (626L)
- `local_diffusion.py` (243L)
- `local_models.py` (193L)
- `matte_cache.py` (126L)
- `multicam_sync.py` (158L)
- `openh264.py` (410L)
- `package_registry.py` (80L)
- `paths.py` (32L)
- `pixel_effects.py` (1034L)
- `processes.py` (22L)
- `prompt_space.py` (74L)
- `proxies.py` (265L)
- `render_document.py` (130L)
- `renderer.py` (1435L)
- `rhythm.py` (148L)
- `sam_video.py` (163L)
- `scenes.py` (110L)
- `security.py` (68L)
- `segmentation.py` (323L)
- `stabilise.py` (209L)
- `store.py` (71L)
- `subject.py` (220L)
- `template_assets.py` (92L)
- `template_library.py` (452L)
- `text_templates.py` (393L)
- `timing.py` (269L)
- `tools.py` (232L)
- `validation.py` (222L)
- `video_source.py` (536L)
- `windows_console.py` (43L)

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

## v0.56.0 delta

Creator commands added: `clip.rejoin`, `clip.freeze-insert`, `clip.reattach`; `clips.split` splits a list at one time in one step. `clip.creator` may now patch `reversed` and `crop`. Clip fields added: `reversed`, `crop` (four edge fractions, 0 to 0.45), `detachedFrom`; `ClipTransform.flipV`; `Track.magnetic` (clips settle gapless from zero in the engine's emit funnel and after each RPC `project.edit` batch); `Timeline` may carry `width`, `height`, `fps`, resolved by `validate_document` so the renderer, export and RPC read the active timeline's format. The engine keeps `baseFormat`, recorded by both save paths and the journal. `POST /api/media/{id}/reverse` builds a chunked reversed intermediate under `DATA_DIR/reversed`; `POST /api/media/{id}/freeze` extracts one full-resolution frame inline.

## v0.57.0 delta

`TextStyle` carries weight, italic, outlineColor, outlineWidth, shadowColor, shadowBlur, shadowX, shadowY, plateColor, plateOpacity, platePadding, plateRadius, lineHeight, letterSpacing, wrapWidth and textOpacity, all optional; `renderer.text_frame` draws them through `wrap_text`, `measure_text` and `paint_text`, which only walks glyphs when letter spacing is set so untracked titles keep the original code path and pixels. `fonts.install_font` keys fonts by content hash; `presets.py` holds `TITLE_STYLES` (ten built-ins, served at `/api/presets/titles`) and accepts base64 font bytes on save. `effect_previews.render` gains the `title` kind, drawing built-ins through the real renderer. `engine/captions.ts` exposes `CaptionOptions`, `captionLook`, `limitWords` and `typedCaptions`; the worker takes a model size and picks WebGPU or WASM.

## v0.58.0 delta

`frame_cache.py` holds `FrameCache` (frames keyed by time plus the signatures of the clips covering that time, with `retarget` dropping only a changed clip's span) and `ReadAhead` (one worker per session rendering ahead of the last request). `render_api.py` serves frames through the cache (`x-formcut-frame: hit|miss`), adds `POST /sessions/{id}/document`, `GET /sessions/{id}/stats` and `POST /clip-audio`, and exports through a bounded pool (`export_workers`, `_render_span`, `FORMCUT_EXPORT_WORKERS`). `audio_render.py` exposes `processed_clip_audio` and `clip_envelope`, shared by the per-clip cache and the exported mix. `video_source.hwaccel_flags` probes hardware decode by decoding, not by listing, with `FORMCUT_HWACCEL=off`. Not yet present: the R3 GPU compositing path, which still needs an adapter to write and measure against.

## v0.59.0 delta

`pixel_effects` gains `COLOUR_PANEL`, `colour_active`, `colour_panel` and `apply_colour_panel`: a thirteen-control correction stage the renderer runs before the effect stack, skipped entirely when a clip has no `colour` object and bit-identical to no panel when neutral. `timing` gains `keyed_value` (effect and volume key sampling with the transform easing modes), `effect_params_at`, `volume_at`, and the animation slots (`IN_PRESETS`, `COMBO_PRESETS`, `animation_at`) which layer multipliers and offsets on the sampled transform so trimming rescales them. `assets.apply_lut` takes an intensity; an imported `.cube` is flagged as a look and listed by `catalogue.imported_looks`, with `effect_previews` drawing `kind="look"` thumbnails through the real LUT path. Masks accept `shape="linear"` with an angle, and `invert` on every shape. `catalogue.AUDIO_PARAMS`, `AUDIO_TEMPLATES` and `audio_chain` template declared strengths into filter text inside the engine. `audio_render.time_stretch` resamples like tape when a clip sets `pitchFollowsSpeed`. `catalogue.PIXEL_PARAMS` and `scale_pixel_params`, with the renderer's per-media `decode_scale`, keep pixel-measured parameters proportional to the resolution actually decoded.

## v0.60.0 delta

`matte_cache.py` holds the background-removal matte store: `matte_key` (media, model and the options that shape a matte; feather is applied at read time instead), `sample_times` (ten per source second, every frame under ten), `store`, `read` with interpolation, `progress` and `clear`; the renderer reads it and never runs inference, and a clip without ready mattes renders unmatted. `POST /api/render/mattes` fills it as a job. `encoders.py` is new: `CANDIDATES` per codec in preference order, `detect` confirming each by encoding two frames, `choose`, `tier_flags` per encoder family, `pixel_format` and `TEN_BIT` for X3, and the fitted `estimate_bitrate` and `estimate_size` for X5 (power law in pixels per second, per-codec quality factors). `render_api` gains `/estimate`, size and rate presets (`resize_for`, `RATE_PRESETS`), and export takes codec, tenBit, size and rate. `media.has_audio` probes and caches whether a file carries sound. `backend/app/export.py` is deleted. `model_manager.WHISPER_MODELS` covers all six Whisper sizes.

## v0.61.0 delta

`effect_packages.py` loads effect packages from `effects/` in the data directory: a manifest plus a filter-chain template (`chain.txt`, parameter slots as `{name}`) or a WGSL shader (`shader.wgsl`); `ALLOWED_FILTERS` is the security boundary, `reload`, `entries`, `failures` and `chain_for` are the surface, and failures are collected with reasons rather than raised. The catalogue, validation and the audio mix accept package ids. `template_assets.gather` now bundles fixed media as well as fonts, LUTs and shaders, and `restore` rewrites `mediaId` alongside the asset fields; `templates.poster_frame` stores a small jpeg drawn from the project as it arrived. `model_manager` gains `PINNED`, `source_for` and `set_source`, and rejects a download whose digest does not match its pin. `main.py` gains a per-run log (last ten kept), `/api/diagnostics`, `/api/diagnostics/log`, `/api/locales` and `/api/packages`. `security.remote_token` gates non-loopback access behind `FORMCUT_REMOTE_TOKEN`. `automation` adds `clip.detach`, `clip.ripple-delete`, `clip.speed-curve` and `clip.animations` and eleven more writable clip properties.
