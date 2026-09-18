# Interface map

Contents: modules, engine commands, emitted names, tokens, stylesheet order.

Derived from `frontend/src` at v0.53.3.

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
- `engine/keyframes.ts` (97L)
- `engine/local-transport.ts` (11L)
- `engine/media.ts` (77L)
- `engine/motion.ts` (25L)
- `engine/persistence.ts` (99L)
- `engine/project.ts` (569L)
- `engine/seed.ts` (43L)
- `engine/timing.ts` (61L)
- `engine/types.ts` (138L)
- `ui/accordion.ts` (55L)
- `ui/appearance.ts` (177L)
- `ui/clip-visuals.ts` (158L)
- `ui/creator-panel.ts` (160L)
- `ui/editor-actions.ts` (61L)
- `ui/effect-parameters.ts` (22L)
- `ui/export-job.ts` (11L)
- `ui/file-menu.ts` (16L)
- `ui/font-tools.ts` (25L)
- `ui/icons-lucide.ts` (28L)
- `ui/icons.ts` (50L)
- `ui/inspector-pane.ts` (521L)
- `ui/media-pane.ts` (804L)
- `ui/preset-grid.ts` (20L)
- `ui/preview-manipulation.ts` (68L)
- `ui/render-preview.ts` (194L)
- `ui/safe-text.ts` (3L)
- `ui/settings-popout.ts` (476L)
- `ui/start-screen.ts` (390L)
- `ui/studio-tools.ts` (164L)
- `ui/timeline-pane.ts` (445L)
- `ui/timeline-structure.ts` (41L)
- `ui/title-speech.ts` (53L)
- `ui/titlebar.ts` (238L)
- `ui/track-controls.ts` (35L)
- `ui/track-keyframes.ts` (371L)
- `ui/tracking.ts` (38L)
- `ui/workspace-layout.ts` (181L)
- `workers/transcription.ts` (84L)
- `i18n/de.json` (283L)
- `i18n/en.json` (283L)
- `i18n/es.json` (283L)
- `i18n/index.ts` (52L)
- `i18n/language-pack.ts` (626L)
- `i18n/text.ts` (29L)
- `styles/app.css` (847L)
- `styles/containers.css` (284L)
- `styles/creator.css` (65L)
- `styles/settings.css` (122L)
- `styles/themes.css` (856L)
- `styles/tokens.css` (68L)

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
- `clip.split`
- `clip.style`
- `clip.text`
- `clip.timing`
- `clip.transform`
- `clip.transition`
- `clip.trim`
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
