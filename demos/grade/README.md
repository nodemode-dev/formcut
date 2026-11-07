# FormCut grade demo

The second FormCut demo: colour and effects on real footage. Open `index.html` by double-clicking it. No backend, no network, no install: every script, style and piece of media is in this folder.

It opens on "Last Light", a 38 second film of six real landscape clips and a CC0 piano piece, each clip graded a different way: a look, wheels, curves, a window on the sun, a vignette that grows over the shot, a speed ramp, and a different transition into every shot. A Compare split in the preview shows the original on the left and the graded picture on the right. Every clip, its photographer and its licence is listed in [`CREDITS.md`](CREDITS.md). The other two demos are linked in the title bar: [Edit](../../demo/index.html) and [Deliver](../deliver/index.html).

## What it shows

The real FormCut state engine, tokens, appearance profiles, icons and the real Color section (`frontend/src/ui/color-section.ts`), mounted unchanged, beside demo 1's timeline. A pixel renderer in the page ports the engine's colour maths so what you see is what the maths gives.

- **Scopes:** waveform, parade, vectorscope and histogram of the frame on screen, from the Color section.
- **Colour:** the four wheels (lift, gamma, gain, offset), primaries, curves, the basic panel and copy and paste of a grade, all through the engine's `clip.colour` command.
- **Looks:** the 20 grade stacks of the engine's effect library with a strength slider, a vignette and grain with keyable amounts, and a dropped `.cube` file as a 3D LUT. The whole grade is evaluated as one 33 point lattice with a trilinear lookup per frame, as the engine does; Export can bake the selected clip's grade into a `.cube`.
- **Masks:** a shape (14 of them), feather, angle and invert on a clip, and Window on Overlay, which copies the clip to the Overlay track as a power window.
- **Keyframes:** position, scale, rotation and opacity and effect amounts through the engine's `clip.keyframe`, a keyframe lane, interpolation, motion presets.
- **Speed ramps:** the engine's speed-curve presets and an editable curve; the picture follows the curve.
- **Transitions:** all 23 engine transition types, with a live swatch of each in the Transitions tab.
- **Export:** a WebM of the timeline (the preview renderer at full size, recorded in real time with the music), a PNG of the current frame, the selected grade as a `.cube`, or the project as JSON.

## Your own files

Drop a video, picture, audio file, `.cube` LUT or `.srt` anywhere on the page, or use Add files. Files are read in this page and never uploaded. The film's media ship as JavaScript data packs in `assets/media/`; Chrome blocks reading local files from `file://`, so each pack is loaded by a script tag on demand, decoded to a Blob or an audio buffer, and swapped in while the bin cards, timeline and thumbnails stay in place.

## Open it

- Double-click `demos/grade/index.html` (a `file://` page), or
- serve the folder with any static server, for example `python3 -m http.server --directory demos/grade 8092`.

Use a current Chromium, Firefox or Safari. WebM export needs `MediaRecorder` with WebM; where it is missing the page says so.

## Rebuild

From this folder, with the app's `frontend/node_modules` installed:

```sh
node ../../frontend/node_modules/vite/bin/vite.js build --config ./vite.config.mjs
node ../../frontend/node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
```

Vite uses `src/index.html` as the entry, a relative base and one IIFE script (module scripts do not load from `file://`), and writes into this folder. The page reuses demo 1's `media.ts`, `timeline.ts`, `exporter.ts`, `captions.ts` and `demo.css` by path and edits none of them.

## Limits

The renderer is a browser canvas, not the Python engine, so it has no planar tracking, device clips or transcription, and the grade is evaluated per frame on the CPU. Export records in real time, so a render takes as long as the film. Rationale for each choice is in `HASHOUT_LOG.md`.
