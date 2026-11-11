# HASHOUT_LOG · interface

Reasoning behind interface changes, newest first.

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
