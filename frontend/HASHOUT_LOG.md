# HASHOUT_LOG · interface

Reasoning behind interface changes, newest first.

## 2.15.4 · a tab drag released off the strip ends

- **What was wrong.** The timeline tab drag listened for `pointerup` and `pointercancel` on the strip only, without pointer capture, so a press on a tab released below the strip never ran `release`. The `pointermove` listener stayed, and moving across the tabs afterwards with no button pressed dispatched `timeline.move` and reordered timelines.
- **What changed.** The move handler releases the drag as soon as it sees a move with the primary button up.
- **Checked.** `tsc --noEmit` is clean. Not verified in a browser.

## 2.15.4 · easing grips follow the pointer and can be undone

- **What was wrong.** In the graph's grip drag, `const index = list.findIndex(...)` shadowed the lane `index`, so `rangeOf(block.prop, clipsOn(index))` read the clips of the track whose number was the keyframe's position, and the handle's y mapping was wrong. Every move dispatched `quiet: true`, including the first, so no history step was pushed and the reshape folded into the previous undo step or could not be undone.
- **What changed.** The key's position is `keyIndex` (and the drag returns when the key is not found), so the range uses the lane's own clips; the first move dispatches without `quiet`, as `dragAlong` does, and later moves stay quiet.
- **Checked.** `tsc --noEmit` is clean. Not verified in a browser.

## 2.15.4 · Delete on box-selected keyframes deletes only the keyframes

- **What was wrong.** `timeline-pane.ts` and `track-keyframes.ts` both listen for Delete and Backspace on the window in the bubble phase, and the timeline's listener was registered first, so with keyframes box-selected and a clip selected (the usual case) Delete removed the clip and then the keys. The keyframe selection was also never cleared, so a later Delete meant for a clip also stripped stale keys.
- **What changed.** The keyframe listener runs in the capture phase and stops the event once it has deleted keys; it still returns early when no keys are selected, so the clip Delete is unchanged then. The selection is cleared on "clip-selection" and "timeline" events.
- **Checked.** `tsc --noEmit` is clean. The timeline pane is built in `main.ts` before `installEditorActions` installs the key layouts, so this listener also runs before a layout that binds Delete or Backspace (the Final Cut Pro layout's ripple delete). Not verified in a browser.

## 2.15.4 · a left trim stops at the start of the media

- **What was wrong.** Dragging a video or audio clip's left edge had no lower bound from its source, and `clip.trim` clamped the new source in to 0 instead of refusing. A fresh clip (source in 0) dragged 2 s left started 2 s earlier and was 2 s longer, so every frame played 2 s earlier than before and the tail read past the end of the media. The browser demo (`demo/src/timeline.ts`) already bounds this.
- **What changed.** The drag records `minStart = start - sourceIn / speedAt(clip, 0)` for video and audio clips and clamps the dragged and snapped start to it. `clip.trim` refuses, with nothing recorded, a video or audio trim whose new source in would fall below 0 (`sourceIn + sourceDelta(clip, offset)`). Text, image and other clips without a timed source are not bounded, as before.
- **Checked.** `tsc --noEmit` is clean. A copy of the engine under `node --experimental-strip-types`: trimming a 5-10 s clip with source in 0 to start at 3 is refused; with source in 4 at speed 2, a start of 3 is accepted (source in 0) and 2.9 refused; a text clip extends freely. The drag itself was not run in a browser.

## 2.15.4 · keyframe sampling eases the way the renderer does

- **What was wrong.** `samplePoints` in `engine/keyframes.ts` used the old `easeProgress` (smoothstep or a quadratic for three names, linear for every other mode) and ignored dragged handles, while the renderer (`backend/app/timing.py` `ease`) and the graph (`timing.ts` `easeAt`) use the cubic-bezier handles. At p 0.3, ease sampled 0.216 against 0.513 rendered, overshoot 0.300 against 0.907, snap 0.300 against 0.018. The inspector's values, the preview's move, scale and crop handles, and lanes-mode "add key here" (which writes the sampled value) all used the wrong curve.
- **What changed.** `samplePoints` calls `easeAt(progress, interp, handles)`; the hold early return stays.
- **Checked.** A copy of the engine under `node --experimental-strip-types` against `property_at` from `backend/app/timing.py` under `python3`: every named mode, hold, a `bezier` with handles and a named mode with handles past the 0 to 1 range, at p 0.1, 0.3, 0.5, 0.7 and 0.9, give identical values to six decimals (60 of 60).

## 2.15.4 · timecode shows the frame the playhead is on

- **What was wrong.** `formatTimecode` took the frame as `floor(fraction of the second * fps)`, which floors values such as 5.9999999, so 1.2 s at 30 fps read 00:00:01:05 and 4.1 s read :02. Frame steps added `n / fps` to the playhead without snapping, so stepping drifted off the frame grid: 22 of the first 90 frames showed the wrong number.
- **What changed.** The timecode counts whole frames once, `floor(seconds * fps + 1e-6)` at the rounded frame rate, and takes frames, seconds, minutes and hours from that count. `transport.step` moves from the frame the timecode shows (`floor(playhead * fps + 1e-6) + n`) and divides back, so every step lands on the grid. Floor rather than round keeps a mid-frame playhead on the frame being shown.
- **Checked.** A copy of the engine under `node --experimental-strip-types`: 1.2 s reads :06 and 4.1 s :03; 3000 steps forward and 3000 back at 30 fps give 0 wrong readouts; every frame time `i/30` over ten minutes reads correctly.

## 2.15.4 · range edits cut tails the way a split does

- **What was wrong.** Lift, Extract, Overwrite, Insert, `clip.remove-range`, and Roll and Slide on the clip after the edit moved a cut clip's source by timeline seconds (`sourceIn + offset`) and copied its keyframes and speed curve unchanged. `clip.split` and `clip.trim` already use `sourceTime`, `shiftedCurve` and `retimedKeys`. On a clip at speed 2 from 0 to 10 s, Lift 2-4 gave the tail source in 4 (a split at 4 gives 8), so the tail replayed footage the head had shown, and its keyframe at 8 stayed at 8 instead of 4.
- **What changed.** One helper, `tailOf(clip, offset, duration)`, beside `carveRange`, returns the clip with source in, speed curve and keyframes moved on by `offset` the way `splitOne` does. Every tail and head-trim in those paths uses it; Roll and Slide apply it to the clip after with the delta, and their "source before its start" check uses `sourceDelta` instead of the raw delta.
- **Checked.** A copy of the engine under `node --experimental-strip-types`, speed-2 clip with a key at 8: Lift 2-4, Extract 2-4 and 0-4, Insert at 4 and remove-range 2-4 all give the tail source in 8 and the key at 4, as `clip.split` at 4 does; with a speed curve from 1 to 3, Lift and split both give source in 5.6. Roll +1 on a speed-2 clip after gives source in 6 and the key at 7, Roll -1 gives 2 and 9, and Roll -1 with only 1 s of source before is refused.

## 2.15.4 · range edits leave locked tracks alone

- **What was wrong.** The dispatch lock guard covers only commands that start with `clip.`. Lift, Extract (`timeline.cut-range`), Insert and Overwrite loop over every track, so a locked track was carved, split or moved by them, from the timeline toolbar, the Pro tab, a key layout or the extension command.
- **What changed.** Lift, Extract and Insert's ripple skip locked tracks, and Insert and Overwrite do nothing when their target track is locked. Extract therefore leaves a locked track where it is.
- **Checked.** A copy of the engine under `node --experimental-strip-types`, a locked 10 s clip beside an unlocked one: Lift, Extract and Insert change only the unlocked track, and Insert or Overwrite aimed at the locked track change nothing.

## 2.15.4 · opening a project starts from a clean slate

- **What was wrong.** `project.load` merged the payload into the state with `Object.assign`, so optional fields the payload did not carry (background, sync folder, output colour) stayed from the previous project, and the engine's marked range (`engine.range`, not part of the document) stayed set: opening B after marking a range in A showed the band on B, and Extract or Lift would cut that span out of B.
- **What changed.** `project.load` removes `background`, clears `syncFolder`, `outputColour` and the marked range before it applies the payload.
- **Checked.** A copy of the engine under `node --experimental-strip-types`: after a sync folder, a background and a range in A, loading B gives no background, sync folder undefined and range null.

## 2.15.4 · a relink is not undone with the edit before it

- **What was wrong.** Undo deltas are computed when the next step starts, as a diff of the current document against the copy taken before the step. `media.relink` changed clip media ids without closing the step in flight, so the next Ctrl+Z after (say) a move also put the old, missing media ids back.
- **What changed.** `media.relink` settles the pending step and clears the fold key before it changes anything. The relink itself stays unrecorded, as before, and no undo reverts it.
- **Checked.** A copy of the engine run under `node --experimental-strip-types`: move a clip, relink "old" to "new", undo, gives start 0 and media id "new" (before the change: "old").

## 2.15.4 · a save clears the recovery journal it replaces

- **What was wrong.** The journal is keyed by the project id, or "unsaved" for a new project. Autosave cleared `journalKey(engine)` after the save, by which time `project.saved` had set the new id, so a new project's "unsaved" journal stayed and the home screen offered to recover a project that was saved (Restore then made a duplicate). The manual save cleared no journal at all, so with autosave off every saved project was offered again at an older revision.
- **What changed.** Both save paths read the key before saving and, on success, clear it and also the post-save key when it differs. The manual save clears only when the document was not edited while the save was in flight.
- **Checked.** `tsc --noEmit` is clean. Not verified against a running backend.

## 2.15.4 · closing Missing media reloads only after a save that worked

- **What was wrong.** Closing the Missing media dialog ran `saveProject` and then `openProject` on the same id without looking at the save's result. When the save failed (a conflict with a newer server copy, or the backend down), the reload replaced the document with the server copy, dropping unsaved edits and the undo history without a word.
- **What changed.** The project is reopened only when the save returns a record; otherwise the titlebar toast says the action did not work and the document stays as it is.
- **Checked.** `tsc --noEmit` is clean. Not verified in a browser.

## 2.15.4 · saves keep the background, sync folder and output colour

- **What was wrong.** `saveProject`, `saveProjectChecked` and the recovery journal sent a fixed field list (title, format, timelines, active timeline, revision). The backend keeps extra fields but replaces the whole record on a save, so a background set in the inspector was lost on the next save, a `syncFolder` or `background` set over RPC was wiped by the next interface save, and the opt-in sync folder never reached the backend from the app.
- **What changed.** The three bodies also carry `background`, `syncFolder` and `outputColour`, and `openProject` and `restoreJournal` read the same keys back into `project.load`. The backend is unchanged.
- **Checked.** `tsc --noEmit` is clean. Not verified against a running backend.

## 2.15.4 · the work area follows the opened project

- **What was wrong.** The work area reloaded only on a "project" event, and `project.load` never emitted one. At start-up it was set from the seed project (0.1 s long), so `{0, 0.2}` was handed to the engine, and after opening a real project from the home screen Space looped over the first 0.2 s. Opening any project also kept the previous one's work area. With no saved area the default was frozen at the duration seen when it loaded.
- **What changed.** `project.load` now emits "project" after its other events. `work-area.ts` keeps no area when none is saved for the project, so the engine plays the whole timeline; the bar draws the whole project span in that case (and repaints on clip and timeline changes), and a drag starts from that span. Double-click still clears back to the whole.
- **Checked.** `tsc --noEmit` is clean. Not verified in a browser.

## 2.15.3 · the last two raw z-index values take a token

- **What moved.** `.fav-star` and `.fx-remove` in `styles/app.css` wrote `z-index: 1`. The scale in `styles/tokens.css` starts at `--z-base: 0`, so `--z-raised: 1` is added and both rules use it. The number is the same, so stacking is unchanged; only the property value was touched.
- **Checked.** `tsc --noEmit` is clean. Not verified in a browser.

## 2.15.0 · the three demo films open in the app

- **What was missing.** The start screen's Demo project chip builds a short project from the four engine sample files in examples/demo; it is not any of the repository demos. High Country (demo/), Last Light (demos/grade) and the Walden talk (demos/deliver) existed only as file:// pages. Now each opens in the app; the old chip stays as it was.
- **One builder per film.** The browser demos' project builders moved into `frontend/src/demos/` and the demos import them by path (they already imported the engine, tokens and icons that way). `film-kit.ts` takes the three helpers the builders need from page modules (caption parsing, word timing, crop keyframes); the demos' own modules re-export them, so their other importers are untouched. The app's tsc and the three demos' tsc all pass on the same files.
- **Media ids.** The builders name media by the demo's ids (film-01, grade-music, talk-voice). The engine seeds a demo's files once and answers with a map from those ids to library items, and `openRepoDemo` swaps each clip's id before `project.load`, with `projectId: null` and `saved: false`, so the film is a new project and nothing of the person's is replaced. It seeks to the time the browser demo opens at and selects the same clip.
- **Where they appear.** A Demos row above the projects (mounted once at build time, so the grid below it never moves), cards reusing `.home-card.is-project`, with the poster in a fixed 16:9 art box so nothing shifts when it loads. A Help menu after Extensions in the titlebar, built like the Extensions menu, and Demo items in the native Help menu calling `window.formcut.actions.openDemo`. Cards and items are found by `data-open-demo` and `data-demo`, never by text.
- **Not carried over.** Page code in the browser demos that is not part of the project stays in the pages: the Grade demo's Compare split and the Deliver demo's ducking, loudness and export presets. The Walden music bed opens at its builder's levels, not ducked.

## 2.14.0 · extension host (Form Extension Contract, API 1)

- **Where things live.** formcut has an in-page titlebar menu bar, so the Extensions menu is a fourth `.menu-item` after View, static in the titlebar markup and so laid out with it before the first paint. It has no command palette; contributed commands are in the menu and as Run chips on each row. The panels formcut keeps are the left pane's tabs, so the Extensions panel is a tab there, built as a library-style view (`{ el, tab, load, pause }`) like Devices and Pro, and contributed dock panels open inside it under the list, one at a time with a tab row when there are several. Dialog panels use `.modal-scrim` and `.modal-panel`.
- **Kit vendored unchanged.** `extensions/host-bridge.ts` is the kit's host file; the app passes handlers to `ExtensionHost` and never edits it. Grants and storage use the kit's own `localStorage` keys (`formext.grants`, `formext.store.<id>`), shared by every formcut window on the origin.
- **One undo step.** History records a snapshot before each mutating command. `ProjectEngine.transaction` sets that snapshot once, makes every `pushHistory` inside the call only count, and settles one delta at the end; if any op throws, the document is put back from the snapshot and nothing is recorded. The touch count also tells `applyOps` when a command silently did nothing (a split outside the clip), which becomes -32004 instead of a false success. History steps have no names in formcut, so `label` is accepted and not shown.
- **An allowlist, not the dispatcher.** `extensions/catalogue.ts` lists 22 edit, 7 view and 3 analysis commands with their argument checks. `engine.dispatch` takes any name, including `project.load` and raw clip objects, so extensions never reach it directly: `clip.add` builds the clip from a library item, captions are built the way the Text tab builds them, patches are filtered to known keys. No transcript or speech command is offered (CLAUDE.md's transcript rules). Analysis commands call the engine's own RPC methods (`media.beats`, `media.scenes`, `media.ducking`).
- **Stable DOM.** Rows are keyed by id and patched field by field; their chip and action rows rebuild only when their key (permissions, panels, commands, state) changes. A reload that finds an extension unchanged leaves its row node and its open dock frame alone; a changed one (new version, or any development extension on Reload) has its frames disposed and its docks reopened. Rows already on screen keep their place when the list changes and new ones are appended (sorted by name only at the next start): inserting a row in sorted position pushed the rows below it down, measured CLS 0.0026 under 4x CPU, and 0 after the change. Opening a dock scrolls it into view, since it sits under the list. The list and the empty state stay hidden until the first answer, inside a tab that is itself hidden at start, so nothing shifts on load.
- **Theme.** formcut's tokens map onto the contract's (`--ground` to `--bg`, `--pane` to `--panel`, `--ink` to `--text`, `--ink-soft` to `--muted`, `--cue` to `--accent`, `--edge-strong` to `--border`, `--radius-m` to `--radius`) plus a few extras. A `MutationObserver` on the root's theme attributes and inline style (where a chosen accent lives) recomputes once per frame and calls `setTheme` only when a value changed.
- **Events.** Engine emits are coalesced per frame: clips, timeline and project become `document.changed`, clip-selection becomes `selection.changed`, transport and a paused seek become `transport.changed`. Playback's per-frame playhead is not forwarded.
- **Toasts.** The toast belongs to `titlebar.ts`; a `formcut:toast` document event lets the extension host use it without a second toast element.
- **Files.** In the desktop app the engine's system dialogs are used (`/api/system/dialogs` says whether they exist). Without them, `files.open` uses `<input type=file>` (the browser's own picker) and `files.save` shows formcut's Save to Downloads dialog with the name selected up to its extension, then the engine writes into Downloads (`name (2).ext` when taken). The first cut used an `<a download>`, which a Tauri webview may ignore and which never told the extension where the file went; the contract's 07:47 wording asks for the confirm-and-downloads fallback.
- **Consent before the frame (integration pass).** Panels open through the kit's `open()`, which awaits consent and only then mounts. The dock's body element is made first and stays detached until consent is given, so Not Now leaves no frame, no dock tab and no row change; the earlier code mounted even after Not Now. A command with a panel goes through the same path and answers -32001 on Not Now. If two opens of the same dock race through consent, the second disposes its frame and selects the first.
