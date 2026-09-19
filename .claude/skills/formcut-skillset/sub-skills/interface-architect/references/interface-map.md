# Interface map

Contents: modules, engine commands, emitted names, tokens, stylesheet order.

Derived from `frontend/src` at v0.56.0.

## Contents

- Modules
- Engine commands
- Emitted names
- Tokens
- Stylesheet order in main.ts

## Modules

- `engine/api.ts` (29L)
- `engine/audio-playback.ts` (164L)
- `engine/captions.ts` (118L)
- `engine/coordinates.ts` (11L)
- `engine/creator-commands.ts` (79L)
- `engine/demo.ts` (57L)
- `engine/json-delta.ts` (49L)
- `engine/keyframes.ts` (97L)
- `engine/local-transport.ts` (11L)
- `engine/media.ts` (77L)
- `engine/motion.ts` (25L)
- `engine/persistence.ts` (233L)
- `engine/project.ts` (768L)
- `engine/seed.ts` (52L)
- `engine/timing.ts` (61L)
- `engine/types.ts` (139L)
- `ui/accordion.ts` (55L)
- `ui/appearance.ts` (177L)
- `ui/clip-visuals.ts` (158L)
- `ui/creator-panel.ts` (160L)
- `ui/editor-actions.ts` (88L)
- `ui/effect-parameters.ts` (76L)
- `ui/export-job.ts` (11L)
- `ui/file-menu.ts` (16L)
- `ui/font-tools.ts` (25L)
- `ui/icons-lucide.ts` (48L)
- `ui/icons.ts` (51L)
- `ui/inspector-pane.ts` (542L)
- `ui/interface-mode.ts` (202L)
- `ui/media-pane.ts` (631L)
- `ui/mode-popout.ts` (157L)
- `ui/preset-grid.ts` (20L)
- `ui/preview-manipulation.ts` (68L)
- `ui/render-preview.ts` (194L)
- `ui/safe-text.ts` (3L)
- `ui/settings-popout.ts` (487L)
- `ui/start-screen.ts` (452L)
- `ui/studio-tools.ts` (302L)
- `ui/timeline-pane.ts` (529L)
- `ui/timeline-structure.ts` (44L)
- `ui/title-speech.ts` (53L)
- `ui/titlebar.ts` (281L)
- `ui/track-controls.ts` (39L)
- `ui/track-height.ts` (80L)
- `ui/track-keyframes.ts` (424L)
- `ui/tracking.ts` (38L)
- `ui/work-area.ts` (135L)
- `ui/workspace-layout.ts` (187L)

## Engine commands

Every way a project can change. Anything outside this list is not a command,
and a UI module that mutates state directly is a defect.

- `captions.add`
- `clip.add`
- `clip.audiofx`
- `clip.effect`
- `clip.interp`
- `clip.key`
- `clip.keyframe`
- `clip.keyframes.set`
- `clip.mask`
- `clip.move`
- `clip.mute`
- `clip.remove`
- `clip.select`
- `clip.select-all`
- `clip.select-set`
- `clip.select-toggle`
- `clip.split`
- `clip.style`
- `clip.text`
- `clip.timing`
- `clip.transform`
- `clip.transition`
- `clip.trim`
- `clips.add`
- `clips.duplicate`
- `clips.move`
- `clips.mute`
- `clips.remove`
- `history.redo`
- `history.undo`
- `media.relink`
- `project.load`
- `project.rename`
- `project.saved`
- `timeline.activate`
- `transport.end`
- `transport.home`
- `transport.seek`
- `transport.step`
- `transport.toggle`

## Emitted names

`clips`, `playhead`, `transport`, `timeline`, `project`, `clip-selection`, and
`noop` for a command the engine does not recognise.
A subscriber filtering on anything else never runs and reports no error.

## Tokens

`--ground`, `--inset`, `--pane`, `--float`, `--control`, `--control-hover`, `--control-press`, `--edge`, `--edge-strong`, `--ink`, `--ink-soft`, `--ink-faint`, `--cue`, `--cue-hover`, `--cue-wash`, `--on-cue`, `--fault`, `--fault-wash`, `--tag-video`, `--tag-video-shade`, `--tag-audio`, `--tag-audio-shade`, `--tag-image`, `--tag-image-shade`, `--tag-text`, `--tag-text-shade`, `--tag-filter`, `--tag-filter-shade`, `--tag-ink`, `--tag-plate`, `--track-bed`, `--track-bed-alt`, `--timescale`, `--now-line`, `--screen`, `--veil`, `--radius-s`, `--radius-m`, `--radius-l`, `--sp-1`, `--sp-2`, `--sp-3`, `--sp-4`, `--sp-5`, `--font-ui`, `--font-mono`, `--z-base`, `--z-clip`, `--z-handles`, `--z-ruler`, `--z-playhead`, `--z-sticky`, `--z-dropdown`, `--z-overlay`, `--z-toast`

## Stylesheet order in main.ts

tokens, creator, app, themes, containers, settings. The shared containering
sheet sits between the app's own styles and the popout's so the popout keeps the
last word about itself; moving it breaks the theme card previews, which lose a
specificity tie decided by source order.

## v0.56.0 delta

Inspector rows: Reverse (`row.reverse`, job-polled with Preparing and Could not prepare), Crop (`row.crop`, stage crop mode with four edge grips), Flip vertical (`row.flipv`). Canvas: alignment guides on the `--guide` token snap moves and corner scales to edges, centre, thirds and other layers within 6 px; Alt bypasses. Track headers gain a magnet toggle. Easy: `ui/tool-tray.ts` (feature id `easy.tray`, hidden in Advanced) drives the same code paths as the Advanced keys, menus, inspector toggles and creator page select through the `editorVerbs` registry; the inspector shows one column per selection kind from the profile's `inspector.views` map via an `easy-hidden` class channel; effect cards carry favourite stars persisted at `formcut.favourites` and a 300 ms hover audition on a throwaway render session. Menu additions: Freeze frame, Reattach audio (partner-probed).
