# Engine and editing contracts

The vanilla TypeScript ProjectEngine owns interactive project state, selection, history, transport and commands. UI modules dispatch commands and update persistent DOM nodes. The FastAPI engine owns project files, media ingestion, model management, rendering and background jobs. It has a separate automation dispatcher. Preserve equivalent edit semantics between both command paths.

Selection is an ordered set (`selection: string[]`) beside the primary (`selectedClipId`, always the set's last id). A plain select collapses the set; `clip.select-toggle`, `clip.select-set` and `clip.select-all` manage it; removal, split, timeline switch and project load keep it in step; selecting is not an edit so `clip.select*` skips the locked-track pre-guard. Group commands (`clips.move`, `clips.remove`, `clips.duplicate`, `clips.add`, `clips.mute`) act on a set as one history step; a group move keeps relative offsets and refuses whole if any member would land on a locked track or before zero. The automation dispatcher mirrors the five with identical semantics.

History holds per-step deltas (`engine/json-delta.ts`), 200 deep, with one full document copy only for the step in flight; a same-key `clip.transform` within 500 ms folds into the open step so a slider or grip drag undoes at once. Autosave writes through the ordinary save path 2 s after the last change (30 s cap, on by default); a 409 keeps the local copy and surfaces a conflict bar. Every unsaved change also journals to `/api/recovery` (`DATA_DIR/recovery/<projectId or unsaved>.json`, atomic replace); a successful save clears the journal and the start screen offers Restore for the newest one.

A project contains ordered timelines and tracks. Clips carry absolute timeline start and duration, sourceIn, optional speedCurve, transform, keyframes, effects, audio effects and asset references. Keyframe times are clip-relative. Source time is sourceIn plus the integral of the speed curve from zero to clip-relative time. A cut changes sourceIn and shifts curve/keyframe times; negative retained keyframes preserve interpolation across the new boundary.

`backend/app/render_document.py` validates every timeline and flattens the active one. It derives transition overlap/ramp metadata without mutating stored clips. `renderer.py` decodes a source frame, applies independent effects/LUT/WGSL, keying/cutout/masks, animated geometry and composition. `audio_render.py` uses the same timing and transition model, phase-vocoder stretching, allowlisted processing chains and stereo mixing. `render_api.py` serves PNG frames and produces MP4/WebM through the same FrameRenderer.

Normal blending composites on the CPU by default because per-layer GPU upload and readback cost more than the blend itself; wgpu handles the other blend modes and custom WGSL. R3 adds the stack path: consecutive layers gather into a run and `gpu.composite_stack` blends them in one device pass through a persistent compositor, the canvas uploaded once and read back once, normal mode included; anything that reads the canvas mid-frame (the Rust kernel, filter clips) flushes the run first, so both paths see identical state. The CPU path stays the reference: `FORMCUT_COMPOSITE=cpu` forces it, `=gpu` forces the stack, and unset engages the stack only on a real accelerator, never a software adapter; `gpu.status()` names the active compositor. Verified within one count of exact float arithmetic, and bit-identical to the CPU path on a rotated three-blend frame, with the stack faster even on llvmpipe because the win is the removed transfers. The remaining pipeline runs on CPU. Since v1.62.0, `gpu_effects.py` runs a clip's grade, fourteen effects and its transform as WGSL passes on a resident layer under the same rule (`FORMCUT_EFFECTS`, the CPU as reference and fallback, the Rust kernel serving the CPU side only); decode, the colour panel, LUTs, masks and transitions stay on the CPU, and the warped layer crosses memory once before the blend. Playback streams JPEG frames from `render_stream.py` on its own renderer while paused frames stay lossless PNG, and preview-bounded decoders are pooled across renderers in `video_source.py`. Do not rename the path "fully GPU" or infer playback throughput from a successful render.

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

A clip whose media cannot be read (not in the library, its file missing, a link to nothing, or a file the decoder
cannot open) is drawn in the preview as a card naming the file and the reason, and said once in the terminal; the rest
of the frame goes on, and the preview stream no longer takes its connection down. An export stops instead, naming the
file and the reason. A video that the device's colour path cannot read is read again with formcut's own conversion.
`cd backend && ./venv/bin/python -m app.media_check` (or GET /api/media/health) reports every item's file and whether
it decodes through both colour paths, and every clip in a saved project whose media the library does not have; it
changes nothing.

Every state file in the data folder is kept the same careful way (`durable.py`): written whole to a temporary
file and moved into place, the version it replaces kept as `<name>.bak`, and a file that cannot be read set aside
as `<name>.damaged-<time>` (never overwritten) with its backup read in its place, rather than read as empty and saved
over. That covers the projects (`projects.json`, each project also kept in `project-records/<id>.json`, which it is
rebuilt from first), the API keys (`providers.json`, owner-only, its backup too), presets, the cloud, TikTok,
Instagram, remote and webhook connections, and the Krea 2 and Klein licence records.

The media library's index (`media.json` in the data folder) is not its only record. It is written whole to a
temporary file and moved into place, the version before it kept as `media.json.bak`, and each item's own record
kept in `media-records/<id>.json`. When the index is missing or unreadable it is rebuilt from those, and from the
files in `media/` themselves (probed afresh, named after the clip that uses them in a saved project, or
"Recovered <kind> <id>"); a media file the index does not know is taken back into it when a clip asks for it and at
start, so a lost index no longer leaves every clip undecodable. Deleting media removes its record, so it does not
come back. Recovery never deletes a file.

Where the device path runs, formcut converts decoded frames to RGB itself
(`backend/app/yuv.py`) rather than through swscale. A planar 4:2:0 frame at its
own size (8-bit, full-range 8-bit, or 10-bit) goes up to the device as its
planes when its layer goes straight there, and the first pass converts it; in
a fused chain, the conversion is the chain kernel's head, so a layer's upload,
conversion, effects and first blend are one dispatch. A frame this side needs
(for a colour panel, a grade, stabilisation, a crop, or a CPU-only effect) is
converted on the decoder's read-ahead thread by the same map through cv2, and
the two agree to a code. The map is bilinear chroma, the stream's own matrix
and range, clipped and rounded half up. Against swscale the difference is the
chroma filter, about a byte count on average at chroma edges. Without a device,
swscale converts as before, so the frame path's exports stay the pictures of the
native-cuts and layered paths, which convert with swscale too. `FORMCUT_YUV=0`
turns formcut's conversion off; `=1` turns it on everywhere, as the bench does
so that it compares the two paths like with like.

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
Preview frames are cached by content and rendered ahead; per-clip audio is cached and mixed live in the interface against the audio clock; export renders on a bounded pool; hardware decode is probed by decoding. The GPU path covers the blend (v1.61.0) and, since v1.62.0, the grade, fourteen effects and the transform as passes in `gpu_effects.py`, each measured within 1/255 of the CPU reference, which stays the fallback; decoded frames still cross memory between the warp and the blend, and a frame-rate reading needs a real adapter.


### v0.59.0
A colour panel runs ahead of the effect stack; effect parameters, volume and animation slots are sampled per frame; pixel-measured parameters scale with the decoded resolution so preview and export agree.


### v0.60.0
Mattes are computed once into a cache and only read at render time; encoders are confirmed by encoding rather than by listing; export size estimates come from a model fitted to real output.


### v0.61.0
Effects can be added as data packages with a filter allowlist; templates carry their own fonts, LUTs, shaders, fixed media and a poster; model downloads are pinned; the RPC surface covers every interface edit.


### v1.56.0 to v1.60.0 (the repository's own numbering, which diverged from the plan's)
Capture remuxes browser recordings in `media.py`; GIF exports go through an ffv1 intermediate into `gif_export.py`'s two-pass palette; HEIC, AVIF and TIFF stills import through Pillow and pi-heif with the fast paths refusing what their ffmpeg cannot decode; HDR sources are tone-mapped in `video_source.py`'s one decode chain so preview and export agree, and the fast paths refuse HDR; a clip's `audioStream` is mapped at the one decode site in `audio_render.py` and keyed into the clip-audio cache. Every registry file is pinned in `model_manager.PINNED`; `model_file()` resolves the model folder first, then `app/bundled_models`, where the build ships U2NetP; `segmentation.cutout_ready` admits the `auto` arbitration; `brush.py` maps strokes to source space for the plain brush and resolves smart strokes through SAM 2 into region outlines that `feathered()` fills; every ONNX Runtime session takes `model_manager.providers()`, platform accelerator first, CPU floor.
