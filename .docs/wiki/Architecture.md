# Engine and editing contracts

The vanilla TypeScript ProjectEngine owns interactive project state, selection, history, transport and commands. UI modules dispatch commands and update persistent DOM nodes. The FastAPI engine owns project files, media ingestion, model management, rendering and background jobs. It has a separate automation dispatcher. Preserve equivalent edit semantics between both command paths.

Selection is an ordered set (`selection: string[]`) beside the primary (`selectedClipId`, always the set's last id). A plain select collapses the set; `clip.select-toggle`, `clip.select-set` and `clip.select-all` manage it; removal, split, timeline switch and project load keep it in step; selecting is not an edit so `clip.select*` skips the locked-track pre-guard. Group commands (`clips.move`, `clips.remove`, `clips.duplicate`, `clips.add`, `clips.mute`) act on a set as one history step; a group move keeps relative offsets and refuses whole if any member would land on a locked track or before zero. The automation dispatcher mirrors the five with identical semantics.

History holds per-step deltas (`engine/json-delta.ts`), 200 deep, with one full document copy only for the step in flight; a same-key `clip.transform` within 500 ms folds into the open step so a slider or grip drag undoes at once. Autosave writes through the ordinary save path 2 s after the last change (30 s cap, on by default); a 409 keeps the local copy and surfaces a conflict bar. Every unsaved change also journals to `/api/recovery` (`DATA_DIR/recovery/<projectId or unsaved>.json`, atomic replace); a successful save clears the journal and the start screen offers Restore for the newest one.

A project contains ordered timelines and tracks. Clips carry absolute timeline start and duration, sourceIn, optional speedCurve, transform, keyframes, effects, audio effects and asset references. Keyframe times are clip-relative. Source time is sourceIn plus the integral of the speed curve from zero to clip-relative time. A cut changes sourceIn and shifts curve/keyframe times; negative retained keyframes preserve interpolation across the new boundary.

`backend/app/render_document.py` validates every timeline and flattens the active one. It derives transition overlap/ramp metadata without mutating stored clips. `renderer.py` decodes a source frame, applies independent effects/LUT/WGSL, keying/cutout/masks, animated geometry and composition. `audio_render.py` uses the same timing and transition model, phase-vocoder stretching, allowlisted processing chains and stereo mixing. `render_api.py` serves PNG frames and produces MP4/WebM through the same FrameRenderer.

Normal blending composites on the CPU because per-layer GPU upload and readback cost more than the blend itself; wgpu handles the other blend modes and custom WGSL. The remaining pipeline runs on CPU. Playback streams JPEG frames from `render_stream.py` on its own renderer while paused frames stay lossless PNG, and preview-bounded decoders are pooled across renderers in `video_source.py`. Do not rename the path "fully GPU" or infer playback throughput from a successful render.

`store.py` saves projects with atomic replace and revision checks. A stale save must not overwrite a newer revision. Frontend saves preserve the dirty flag if editing continues during an asynchronous save. Backend RPC edits are one history transaction; history is process-local.

Background work uses `jobs.py`, with two workers and up to eight active jobs. Status, progress, cancellation and file retrieval have one contract. Model installation and speech use this queue. Reference-counted long-lived assets are not yet implemented; media/assets are retained independently of individual project files.

Writable state comes from `paths.py`. No runtime writes belong under frontend assets or a PyInstaller extraction directory. HTTP binds to loopback. Mutating API clients send `x-formcut-local: 1`; the middleware also rejects non-loopback hosts/origins. Web page code has no Tauri shell permissions.

Keep code comments short; the reasoning behind a change belongs in its commit message. Make manual, single-region edits; do not use bulk replacement or codemods. Preserve mounted controls and their focus. Static creation before mounting is allowed; inspect update paths separately. Every version is driven in a real browser before it is released.

## Playback and decoding

Playing streams JPEG frames from a dedicated renderer over
`/api/render/sessions/{id}/stream`, paced to the wall clock from the moment the
request arrives, with catch-up capped below the decoder's forward-skip window so
a stream never cold-seeks mid-play. The body is disconnect-aware: aborting a
stream closes its renderer from a background thread under the render guard.
Paused and scrubbed frames still come from the lossless PNG frame endpoint, so a
still frame matches export exactly.

Sources decode no larger than the preview canvas when a preview width is given;
exports pass no width and decode at full resolution. Idle preview-bounded
decoders return to a small pool keyed by path and decode size, each remembering
its last frame, and a renderer takes the decoder positioned closest before the
frame it needs. Stills are bounded to preview size, and a still whose effect
stack is only colour grades is prepared once per renderer rather than every
frame.

## Secrets and environment

Keys are read from the environment by the engine, never from the interface or a
project file. `example.env` is the tracked template; copy it to `.env`, which
the launchers export before starting. `.env` is ignored by git.

## Engine services

- `app/providers.py` holds provider keys in the engine (stored first, then the
  environment, never returned) and runs a real connection test per provider.
- `app/clip_visuals.py` serves audio peaks and filmstrips describing whole
  media, cached on disk, so the timeline windows a cached whole instead of
  asking for a render per trim.
- `app/storage.py` measures the data directory by area and marks which areas are
  rebuildable.
- `app/orchestration.py` carries orchestration sessions, the operation log and
  the server-sent event stream that jobs publish to.
- `mcp/` is a separate process: an MCP server over the engine, with its own
  virtualenv because the MCP SDK and the engine's FastAPI disagree on starlette.
- `frontend/src/engine/audio-playback.ts` schedules the decoded mix and acts as
  the transport's clock source; `frontend/src/ui/clip-visuals.ts`,
  `track-keyframes.ts`, `accordion.ts`, `settings-popout.ts` and `appearance.ts` are the
  interface modules added over the same period.
- `.claude/skills/formcut-skillset/` describes this codebase for local
  development, generated from the tree rather than written from memory.


### v0.56.0
Per-timeline formats resolve at `validate_document`; reversed intermediates cache under `DATA_DIR/reversed`; magnetic tracks settle in the engine's emit funnel and after each RPC batch.


### v0.57.0
Title styling is drawn entirely in `renderer.text_frame`; fonts install once by content hash; built-in title styles and their engine-rendered thumbnails live in `presets.py` and `effect_previews.py`.


### v0.58.0
Preview frames are cached by content and rendered ahead; per-clip audio is cached and mixed live in the interface against the audio clock; export renders on a bounded pool; hardware decode is probed by decoding. The GPU compositing path is still open.


### v0.59.0
A colour panel runs ahead of the effect stack; effect parameters, volume and animation slots are sampled per frame; pixel-measured parameters scale with the decoded resolution so preview and export agree.


### v0.60.0
Mattes are computed once into a cache and only read at render time; encoders are confirmed by encoding rather than by listing; export size estimates come from a model fitted to real output.


### v0.61.0
Effects can be added as data packages with a filter allowlist; templates carry their own fonts, LUTs, shaders, fixed media and a poster; model downloads are pinned; the RPC surface covers every interface edit.
