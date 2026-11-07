# HASHOUT_LOG: demos/deliver

Why the deliver demo is built the way it is. Dates are 2026-11-07.

## Focus and what was replaced

The brief asked for an interview or talk edit with captions from an SRT, ducking and levels, chapter markers, vertical reframing and export presets. Checked against the repo:

- Chapter markers exist as timeline markers (`marker.add`, `marker.update`, `marker.remove`, `TimelineMarker`), but there is no chapter export. The demo uses real markers and writes the chapter list and a WebVTT chapters file itself; the README says so and the demo never claims them as FormCut features.
- Captions: SRT and VTT import and SRT export exist in the app, word times follow `wordTimes`, and `TextStyle.wordStyle` has the five modes the demo offers. SCC export is not reproduced.
- Ducking and reframing exist in the engine (`rhythm.ducking`, `subject.reframe`) and are ported, not invented.
- Loudness: the engine's export rule is `min(target - integrated, ceiling - true_peak)`; the demo applies it as a master trim and has no limiter, so a target the ceiling forbids is reported as held by the ceiling instead of being forced.

## Interview versus talk

A single speaker reading over footage, not an interview with two voices. No recording of an interview with a freely licensed, non-identifiable speaker was found; a LibriVox reading of Thoreau (public domain, no person on screen) gives the same editing problems: speech over music, captions timed to words, chapters.

## Reuse by path, not by copy

Demo 1's `media.ts` (source registry, pack loader, probes), `timeline.ts` and the SRT parser are imported from `../../demo/src`; the Grade demo's frame renderer (`drawFrame`, transitions, keyframed transforms) is imported from `../grade/src/render.ts`. A caption pass is drawn on top in `src/render.ts`, with the Captions track hidden from the shared renderer, because the shared text drawer has no word styles. The timeline module takes no markers or tab changes, so the page swaps its single tab for two and adds the app's own `.tl-markers` and `.tl-marker` classes to the ruler after it is built.

The engine's `engine/captions.ts` is not imported: it pulls the transcription runtime in, which grew the build by 27 MB. `wordTimes` is four lines and lives in `src/captions.ts`.

## Audio

`src/audio.ts` owns the mixer. One graph builder schedules the clips for the live context and for the offline render, so the loudness figures describe exactly what plays and what is exported. Volume keyframes (what the engine's ducking writes) multiply the clip volume and are written as short linear steps into the gain parameter. The tap that feeds the WebM recorder is the master gain, so the trim is in the file. Meters read an analyser per track bus.

Measurement is BS.1770: two K-weighting biquads, 400 ms blocks every 100 ms, an absolute gate at -70 and a relative gate 10 LU below. The result matched `ffmpeg ebur128` on the exported WAV to 0.1 LU. True peak interpolates three points between samples with a cubic; it is an estimate and labelled so.

## Reframe

A 16:9 clip in a 540 x 960 timeline needs scale 316 percent so the picture covers the frame, and a horizontal position of `(0.5 - centre) * scale` percent to put the crop's centre in the middle. The app's own reframe button writes `posX = (0.5 - centre) * 200` with no scale, because its renderer fits differently; this renderer is contain-fit, hence the different factor. The paths come from `subject.reframe` run on the shipped clips (frames at 2 per second, 480 px grey); the in-page port reproduces its Laplacian (reflect-101 border), the motion term and the two-pass smoothing, and agrees with the engine to about 1 percent of frame width on the stream clip. This footage is slow, so the windows move little; that is what the engine returned, and it is not exaggerated.

## Vertical size

540 x 960 rather than 720 x 1280. A 9:16 window of a 1280 x 720 picture is 405 pixels wide; at 540 the enlargement is 1.33 times and the result is clean, at 720 it is 1.78 times and soft. Pexels footage at 1280 x 720 is the media budget's ceiling.

## Presets and the export dialog

The dialog is the app's own `modal-scrim` and `modal-panel export-panel`. A preset picks the timeline, the target and whether captions are burned in or left as a sidecar; Export fits the loudness first (offline, twice) and then records. Real-time recording was kept from demo 1 because MediaRecorder on a canvas is the only encoder a `file://` page has.

## Not claimed

SCC export, MP4 or codec choice, posting to a platform, chapter embedding in a file, a limiter, speech recognition in the page.

## Zero flash

The theme is set before first paint; media packs decode into reserved cards and clips; the transport, meters and list rows patch text, classes and transforms in place and never rebuild a container; the dialog is mounted hidden. The meters animate by `transform` on fixed bars.

## Size

Eight clips at CRF 27, a mono 80 kbps voice and a 112 kbps music bed: about 24 MB of packs inside the 40 MB budget.
