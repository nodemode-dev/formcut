# FormCut deliver demo

The third FormCut demo: captions, audio and delivery. Open `index.html` by double-clicking it. No backend, no network, no install: every script, style and piece of media is in this folder.

It opens on a finished 86 second talk edit, "Why I went to the woods": a public-domain reading of Thoreau's Walden over eight real landscape clips and a CC0 piano piece, with captions, titles, chapters and a music bed already ducked under the voice. Every clip, its photographer and its licence is listed in [`CREDITS.md`](CREDITS.md). The other two demos are linked in the title bar: [Edit](../../demo/index.html) and [Grade](../grade/index.html).

## What it shows

The real FormCut state engine (`frontend/src/engine/project.ts`: commands, history, timing, keyframes, markers), the real design tokens, appearance profiles and `app.css`, the real inline icons, and demo 1's timeline editor. Page code stands in for the Python engine's renderer, mixer and measurements.

- **Captions from a file:** the talk's captions are an SRT. Import an `.srt` or `.vtt` (or drop one anywhere) and it replaces them; word timing follows the engine's rule (a caption's span shared by character). Word style (highlight, pop, box, reveal, rise), size and placement apply to every caption. Click a cue to seek, edit its text in the Caption tab, export `.srt` or `.vtt`.
- **Audio mixing:** a Voice and a Music track with level faders (written as clip volume), live peak and RMS meters, and Duck under speech: the engine's `ducking()` (`backend/app/rhythm.py`) ported to TypeScript, with its defaults, reading the voice clip and writing volume keyframes on the music clip. The envelope is drawn over the voice's waveform.
- **Loudness:** the mix is rendered offline, K-weighted and gated as ITU-R BS.1770 describes, and reported as integrated loudness, loudness range and true peak. Normalise sets a master trim by the engine's rule, the smaller of the gain to the target and the gain to the true-peak ceiling. Targets: streaming -16 LUFS, shorts -14, EBU R128 -23, ATSC A/85 -24.
- **Chapters:** markers on the ruler (`marker.add`), listed and editable in the Chapters tab, exported as a chapter list and a WebVTT chapters file. Those two exports are written by this demo; FormCut itself has markers but no chapter export.
- **Vertical reframe:** a second timeline, Vertical 9:16 at 540 x 960, shows each 16:9 clip through a 9:16 window written as scale and position keyframes. Paths for the shipped clips come from running the engine's own `reframe()` (`backend/app/subject.py`); Analyse selected clip and Analyse all clips run a TypeScript port of it in the page on the actual pixels, so any clip you drop can be reframed too. Safe zones for the format can be shown over the preview.
- **Export presets:** landscape with burned captions, vertical with burned captions, landscape with an `.srt` beside it, an EBU R128 audio master (16-bit WAV), and captions with chapters. Videos are recorded in real time as WebM with the mixed sound. Each export ends with a report: integrated loudness, true peak, trim, size, length.

## Your own files

Drop a video, audio file, picture, `.srt` or `.vtt` anywhere on the page, or use Add files. Files are read in this page and never uploaded. The talk's media ship as JavaScript data packs in `assets/media/` (`film.js` is the manifest; `talk-01.js` to `talk-08.js`, `voice.js` and `music.js` hold base64 files). Chrome blocks reading local files from `file://`, so each pack is loaded by a script tag on demand, decoded to a Blob or an audio buffer, and swapped in while the bin cards, timeline and thumbnails stay in place.

## Open it

- Double-click `demos/deliver/index.html` (a `file://` page), or
- serve the folder with any static server, for example `python3 -m http.server --directory demos/deliver 8091`.

Use a current Chromium, Firefox or Safari. WebM export needs `MediaRecorder` with WebM; where it is missing the page says so and the WAV and text exports still work.

## Rebuild

From this folder, with the app's `frontend/node_modules` installed:

```sh
node ../../frontend/node_modules/vite/bin/vite.js build --config ./vite.config.mjs
node ../../frontend/node_modules/typescript/bin/tsc --noEmit -p tsconfig.json
```

Vite uses `src/index.html` as the entry, a relative base and one IIFE script (module scripts do not load from `file://`), and writes into this folder. The page reuses demo 1's `media.ts`, `timeline.ts` and `exporter.ts` and the Grade demo's frame renderer by path; it edits none of them.

## Limits

The renderer is a browser canvas, not the Python engine. Export records in real time, so a render takes as long as the film and its frame rate depends on the machine. The true peak is a four-times interpolated estimate. The reframe window follows motion and detail on this footage, which is mostly slow, so the shipped paths are gentle. Rationale for each choice is in `HASHOUT_LOG.md`.
