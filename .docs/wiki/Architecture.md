# Engine and editing contracts

The vanilla TypeScript ProjectEngine owns interactive project state, selection, history, transport and commands. UI modules dispatch commands and update persistent DOM nodes. The FastAPI engine owns project files, media ingestion, model management, rendering and background jobs. It has a separate automation dispatcher. Preserve equivalent edit semantics between both command paths.

A project contains ordered timelines and tracks. Clips carry absolute timeline start and duration, sourceIn, optional speedCurve, transform, keyframes, effects, audio effects and asset references. Keyframe times are clip-relative. Source time is sourceIn plus the integral of the speed curve from zero to clip-relative time. A cut changes sourceIn and shifts curve/keyframe times; negative retained keyframes preserve interpolation across the new boundary.

`backend/app/render_document.py` validates every timeline and flattens the active one. It derives transition overlap/ramp metadata without mutating stored clips. `renderer.py` decodes a source frame, applies independent effects/LUT/WGSL, keying/cutout/masks, animated geometry and composition. `audio_render.py` uses the same timing and transition model, phase-vocoder stretching, allowlisted processing chains and stereo mixing. `render_api.py` serves PNG frames and produces MP4/WebM through the same FrameRenderer.

Normal blending composites on the CPU because per-layer GPU upload and readback cost more than the blend itself; wgpu handles the other blend modes and custom WGSL. The remaining pipeline runs on CPU. Playback streams JPEG frames from `render_stream.py` on its own renderer while paused frames stay lossless PNG, and preview-bounded decoders are pooled across renderers in `video_source.py`. Do not rename the path "fully GPU" or infer playback throughput from a successful render.

`store.py` saves projects with atomic replace and revision checks. A stale save must not overwrite a newer revision. Frontend saves preserve the dirty flag if editing continues during an asynchronous save. Backend RPC edits are one history transaction; history is process-local.

Background work uses `jobs.py`, with two workers and up to eight active jobs. Status, progress, cancellation and file retrieval have one contract. Model installation and speech use this queue. Reference-counted long-lived assets are not yet implemented; media/assets are retained independently of individual project files.

Writable state comes from `paths.py`. No runtime writes belong under frontend assets or a PyInstaller extraction directory. HTTP binds to loopback. Mutating API clients send `x-formcut-local: 1`; the middleware also rejects non-loopback hosts/origins. Web page code has no Tauri shell permissions.

Keep comments and development explanations in the planning sidecar's reasoning logs, not inline in code. Make manual, single-region edits; do not use bulk replacement or codemods. Preserve mounted controls and their focus. Static creation before mounting is allowed; inspect update paths separately. Every version is driven in a real browser, and the flows each one claims are listed in that version's build notes.

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
