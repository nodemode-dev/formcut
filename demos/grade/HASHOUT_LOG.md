# HASHOUT_LOG: demos/grade

Why the grade demo is built the way it is. Dates are 2026-11-07.

## Focus and what was replaced

The brief asked for colour and effects on real footage: scopes, looks, a LUT, masks, keyframes, speed ramps, transitions, a before and after, and an export. Checked against the repo before building:

- The Color section (`frontend/src/ui/color-section.ts`) already holds the wheels, primaries, curves and scopes, so the page mounts it unchanged and does not rewrite it.
- The engine's effect library has 20 grade stacks; the demo reads them as data (`src/looks.ts`) instead of inventing looks.
- `.cube` import and 3D LUT application exist in the engine; the page ports the lattice maths and says so.
- Planar tracking, device clips and transcription are not reproduced and not claimed.

## One lattice per clip

The grade is a chain of stages (panel, wheels, curves, looks, LUT). Running the chain on every pixel was too slow in a canvas, so each clip's chain is evaluated once on a 33 point lattice, cached by a key of the clip's grade, and each frame is a trilinear lookup. This is the engine's own approach, so the picture and the baked `.cube` agree. Checked: the exported `.cube` applied with `ffmpeg lut3d` to the original frame gave a mean colour within about one level of the page's graded frame, RMS difference 2 to 4 levels.

## Flattened source

Pexels footage is already graded and contrasty. Each clip is flattened on encode (`eq=contrast=0.80:saturation=0.74:brightness=0.025`) so a grade has range; CREDITS.md and the Media tab say so. This is a modification of the file, allowed by the Pexels licence.

## Reuse by path

Demo 1's `media.ts`, `timeline.ts`, `exporter.ts`, `captions.ts` and `demo.css` are imported from `../../demo/src`; none is edited. The Compare split, vignette, grain and masks are drawn in `src/render.ts`, which the Deliver demo reuses.

## Media

Six Pexels clips (five distinct sources; two clips are different spans of the same sunset file) and one CC0 Goldberg variation. Each licence was read on its source page. Nothing from `examples/demo`. Sizes: 1280x720 at CRF 25 and a 128 kbps music bed, 26 MB in all against a 40 MB budget.

## Export

A WebM recorded from the preview renderer in real time with the music, a PNG of the frame, the `.cube` of the selected grade, the project JSON. A real export of the film ran 39 s at 1280x720, VP9 and Opus, and its frames matched the preview.

## Not claimed

Colour management between spaces, HDR, a limiter, GPU rendering, tracking.

## Zero flash

The theme is set before first paint; media packs decode into reserved cards; the inspector patches values in place; the link row and the Compare handle are mounted once.
