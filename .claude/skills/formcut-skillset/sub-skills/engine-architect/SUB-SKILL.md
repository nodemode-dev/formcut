---
name: engine-architect
description: >-
  The Python FastAPI engine: module and route map, the shared renderer, the job runner, and the refusal and caching conventions a new endpoint follows.
---

# engine architect

The Python engine: 44 modules under `backend/app`, about eighty routes, one shared renderer, one job runner. Load `references/engine-map.md` for the module and route inventory.
- `references/effect-packages.md`: data-defined effects: the stack format, the loader's rules, where each piece lives, and how to add a look, a grade setting or an effect parameter.

## How it is put together

`main.py` builds the FastAPI app, holds `APP_VERSION`, binds loopback, adds the local-only middleware and includes the routers listed in `features.py`. Mutating calls carry `x-formcut-local`. `paths.py` resolves the data directory, honouring `FORMCUT_DATA_DIR`, and everything persistent lives under it: media, projects, templates, renders, thumbs, peaks, filmstrips, models, the speech runtime, provider keys.

`features.py` mounts every feature router in one tuple. Three routers were once written into the body of that loop instead of its tuple, so each was mounted once per module in it: thirteen copies of each route, with no symptom because FastAPI resolves the first match. When adding a router, read the block rather than appending after the last include.

## The renderer and the jobs

`renderer.py` decodes, applies effects, masks, grades and transforms, and composites. Preview and export both go through it, which is the reason a frame you approve is the frame you ship. `video_source.py` bounds decode to the preview size when a width is given and pools idle preview decoders keyed by path and decode size, each remembering its last frame; the pool hands out the decoder positioned closest before the frame requested. Exports pass no width and their decoders are never pooled.

`jobs.py` runs work on a two-worker pool with an eight-job ceiling, returns `{"job_id": ...}` immediately, and publishes state to the orchestration stream: running, progress every five percent, then done, cancelled or error. Anything that takes more than a moment is a job, and callers poll or subscribe.

## Conventions that matter

- **Refuse clearly.** A missing key, a rejected key and an unreachable endpoint are three different answers. `providers.py` and `local_speech.py` are the models to copy: say what is wrong and what to do.
- **Never return a credential.** Provider state carries configured, source and the last four characters only. The store is written 0600.
- **Cache on disk, keyed by what the answer depends on.** Peaks and filmstrips describe whole media, not a clip, so a trim or zoom slices a cached whole instead of triggering a render.
- **Ingest moves its input.** `media.ingest_path` moves the file it is given, which is right for a temporary render output and destructive for a caller's own file. Any boundary that accepts someone else's path copies first.
- **Validate anything headed into ffmpeg.** Effect and colour strings reach `filter_complex`; `validate_effect` treats them as untrusted input.
