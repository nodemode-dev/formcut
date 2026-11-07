# FormCut demo

An offline editor you can open by double-clicking `index.html`. No backend, no network, no install: every script, style and sample is in this folder.

## What it shows

The real FormCut state engine (`frontend/src/engine/project.ts`, with its undo history, timing and commands), the real design tokens, appearance profiles and `app.css`, and the real inline icon module, driving a timeline editor whose renderer and mixer run in the page instead of the Python engine.

- **Timeline editing:** select, move across tracks, trim by the edges, blade, split at the playhead (S), ripple delete, mark in and out then Extract or Lift, undo and redo, zoom, snapping.
- **Color:** exposure, brightness, contrast, saturation, temperature, tint, fade and vignette per clip, with a live luma waveform of the preview frame.
- **Effects and transitions:** blur, grayscale, sepia, invert, hue shift, pixelate; crossfade, dip, wipes, slide, zoom; speed, fades and volume.
- **Captions:** import an `.srt` or `.vtt` file onto the Titles track, or export the title clips as `.srt`.
- **Probe:** the Media tab reports size, duration, measured frame rate, decoders this browser has, peak and RMS level of any file you add.
- **Export:** a WebM of the timeline (the preview renderer at full size, recorded in real time with the mixed sound), a PNG of the current frame, the captions, or a project `.json` you can open again.

## Your own files

Drop a video, audio file, image, `.srt`, `.vtt` or a project `.json` anywhere on the page, or use Open files. Files are read in this page and never uploaded. With nothing dropped it runs on built-in samples: generated waves, embers, a test pattern, a gradient plate and a synthesised chord loop. None of them is a file; they are drawn and synthesised in code.

## Open it

- Double-click `demo/index.html` (a `file://` page), or
- serve the folder with any static server, for example `python3 -m http.server --directory demo 8090`.

Use a current Chromium, Firefox or Safari. Color and effects use the canvas `filter` property, and WebM export needs `MediaRecorder` with WebM; where either is missing that part is unavailable and the page says so.

## Rebuild

From `frontend/` after `npm ci`:

```sh
npm run demo
```

That runs Vite with `demo/vite.config.mjs`: entry `demo/src/index.html`, relative base, one IIFE script (module scripts do not load from `file://`), output into this folder. `npx tsc --noEmit -p ../demo/tsconfig.json` type-checks the sources. The dev server is `npx vite --config ../demo/vite.config.mjs` on 127.0.0.1:3042.

## Limits

The renderer is a browser canvas, not the Python engine, so it has no keyframes, masks, LUTs, planar tracking, device clips or transcription. Export records in real time and its length is the timeline's length. Two clips cut from the same video file each get their own decoder, so very large files are heavy to cut up. Rationale for each choice is in `HASHOUT_LOG.md`.
