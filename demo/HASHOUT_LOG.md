# HASHOUT_LOG · demo

Reasoning behind the demo, newest first.

## 2.13.0 · offline demo

- **Why the real UI was not run against a shim.** The interface's preview, thumbnails, waveforms and render all call the Python engine, so a fetch shim would have meant rewriting the engine in the page. The demo instead reuses what is pure: `ProjectEngine` and its commands, `timing.ts`, `types.ts`, the tokens, themes, `app.css`, `containers.css`, `creator.css` and `icons.ts`, and adds a canvas renderer and a Web Audio mixer behind the same state engine.
- **One renderer for preview and export.** `render.ts` draws every frame, preview and file. Export switches the preview to full size and records its canvas with `captureStream` and the mixer's `MediaStreamAudioDestinationNode`, so what is seen is what is written. It runs in real time because `MediaRecorder` has no faster mode.
- **Classic script, not a module.** Chrome refuses `type="module"` scripts from `file://`, so `vite.config.mjs` builds one IIFE and moves the tag to the end of the body without `crossorigin`. The config is a plain object so it needs no import of `vite` from outside `frontend/node_modules`.
- **Samples are code.** The repo's `examples/demo` media is third-party (Pexels) and stays out. Waves, embers, a test pattern, a plate and a chord loop are drawn and synthesised at load, so they carry no licence and add no bytes. The test pattern exists so the luma waveform has something to read.
- **Crossfades overlap in the renderer, not on the timeline.** A clip with `transitionIn` also draws the clip that ends where it starts, continued past its end for the transition's length, so abutting clips cross-dissolve without being moved.
- **Timeline nodes are patched in place.** Clips are keyed by id and moved between lanes by re-parenting; ticks are a growing pool. Dragging moves nodes directly and dispatches one engine command on release, so a drag is one undo step and nothing rebuilds.
- **Theme before paint.** `index.html` sets `data-theme` from `localStorage` in an inline script before the stylesheet applies, with its own key so it never reads the desktop app's settings.
- **No new dependency.** Vite and TypeScript are already in `frontend/package.json`; nothing is added to `NOTICE` or `Licences.md`.
- **Not run here.** Safari, Firefox and audible output were not exercised; sound was checked by decoding an exported file and reading its level.
