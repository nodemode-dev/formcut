# Interface map

Contents: modules, engine commands, emitted names, tokens, stylesheet order.

The module list and the engine commands are generated from `frontend/src` by
`python setup/skill_maps.py`; the rest is written by hand.

## Contents

- Modules
- Engine commands
- Emitted names
- Tokens
- Stylesheet order in main.ts

## Modules

- `engine/api.ts` (29L)
- `engine/audio-playback.ts` (164L)
- `engine/captions.ts` (224L)
- `engine/coordinates.ts` (11L)
- `engine/creator-commands.ts` (213L)
- `engine/demo.ts` (58L)
- `engine/json-delta.ts` (49L)
- `engine/keyframes.ts` (97L)
- `engine/live-mix.ts` (156L)
- `engine/local-transport.ts` (11L)
- `engine/media.ts` (79L)
- `engine/motion.ts` (25L)
- `engine/persistence.ts` (237L)
- `engine/project.ts` (1052L)
- `engine/seed.ts` (52L)
- `engine/timing.ts` (96L)
- `engine/types.ts` (277L)
- `i18n/index.ts` (211L)
- `i18n/language-pack.ts` (1156L)
- `i18n/text.ts` (29L)
- `main.ts` (96L)
- `types/assets.d.ts` (6L)
- `ui/accordion.ts` (55L)
- `ui/appearance.ts` (213L)
- `ui/category-icons.ts` (37L)
- `ui/clip-visuals.ts` (158L)
- `ui/cloud.ts` (313L)
- `ui/color-section.ts` (509L)
- `ui/compact.ts` (10L)
- `ui/creator-panel.ts` (361L)
- `ui/editor-actions.ts` (155L)
- `ui/effect-parameters.ts` (78L)
- `ui/export-job.ts` (27L)
- `ui/file-menu.ts` (16L)
- `ui/font-tools.ts` (25L)
- `ui/icons-lucide.ts` (48L)
- `ui/icons.ts` (54L)
- `ui/inspector-pane.ts` (1603L)
- `ui/instagram.ts` (185L)
- `ui/interface-mode.ts` (246L)
- `ui/keyed-list.ts` (12L)
- `ui/library-view.ts` (145L)
- `ui/media-pane.ts` (1233L)
- `ui/mode-popout.ts` (157L)
- `ui/preset-grid.ts` (20L)
- `ui/preview-manipulation.ts` (559L)
- `ui/remote-settings.ts` (93L)
- `ui/render-preview.ts` (235L)
- `ui/safe-text.ts` (3L)
- `ui/settings-link.ts` (8L)
- `ui/settings-popout.ts` (609L)
- `ui/start-screen.ts` (638L)
- `ui/studio-tools.ts` (673L)
- `ui/tiktok-dialog.ts` (258L)
- `ui/tiktok-settings.ts` (89L)
- `ui/timeline-pane.ts` (697L)
- `ui/timeline-structure.ts` (50L)
- `ui/title-speech.ts` (53L)
- `ui/titlebar.ts` (438L)
- `ui/tool-tray.ts` (146L)
- `ui/track-controls.ts` (39L)
- `ui/track-height.ts` (80L)
- `ui/track-keyframes.ts` (666L)
- `ui/tracking.ts` (49L)
- `ui/upscale-dialog.ts` (254L)
- `ui/voiceover.ts` (229L)
- `ui/webhooks-settings.ts` (124L)
- `ui/work-area.ts` (139L)
- `ui/workspace-layout.ts` (305L)
- `workers/transcription.ts` (138L)

## Engine commands

Every way a project can change. Anything outside this list is not a command,
and a UI module that mutates state directly is a defect.

- `captions.add`
- `clip.add`
- `clip.audiofx`
- `clip.colour`
- `clip.cutout`
- `clip.effect`
- `clip.effects`
- `clip.interp`
- `clip.key`
- `clip.keyframe`
- `clip.keyframes.replace`
- `clip.keyframes.set`
- `clip.mask`
- `clip.mask-track`
- `clip.move`
- `clip.mute`
- `clip.remove`
- `clip.remove-range`
- `clip.select`
- `clip.select-all`
- `clip.select-set`
- `clip.select-toggle`
- `clip.smooth-slow`
- `clip.split`
- `clip.stabilise`
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
- `clips.split`
- `history.redo`
- `history.undo`
- `media.relink`
- `project.background`
- `project.load`
- `project.rename`
- `project.saved`
- `timeline.activate`
- `timeline.move`
- `timeline.rename`
- `transport.end`
- `transport.home`
- `transport.seek`
- `transport.skip`
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

## v0.57.0 delta

The inspector's text section gains eleven rows for the full title style, all on the `data-xkey` channel with per-property bounds; blanking a numeric row clears the property. Double-clicking a selected title on the canvas opens `.canvas-typing`, committing one `clip.text` patch per session. The Text tab gains the title style gallery (`/api/presets/titles`, thumbnails from `/api/catalogue/preview/title/{id}`), the caption sheet rows (model, words per caption, placement, size), a cancel chip, and the typed-captions box.

## v0.58.0 delta

`engine/live-mix.ts` adds `LiveMixer`: `warm` fetches each audible clip's processed buffer once from `/api/render/clip-audio`, `play` schedules one source per clip against the audio context clock with fades, volume and pan written as 50 Hz automation matching the export's gain law, and `retune` rewrites one clip's curve in place so a gain edit needs no render. Exposed as `window.formcut.liveMix`.

## v0.59.0 delta

Types gain `ColourPanel` with `COLOUR_NEUTRAL`, `ValueKey` for effect and volume keys, `ClipAnimations` with `IN_ANIMATIONS` and `COMBO_ANIMATIONS`, `lutIntensity`, `pitchFollowsSpeed`, and the linear mask shape with `angle` and `invert`. `clip.creator` may patch `colour`, `pitchFollowsSpeed`, `lutIntensity`, `volumeKeys` and `animations`.

## v0.60.0 delta

The inspector gains an Easy `section.removebg` with Off, Automatic, Brush and Chroma key plus feather and brush sliders and job progress, writing the same cutout and key fields Advanced writes. The export sheet gains codec choices filled from `/api/render/status`, size presets, a 10-bit toggle and a live estimate from `/api/render/estimate` that refreshes on open and on every option change; `exportProject` carries codec, tenBit, size and rate.

## v0.61.0 delta

`ui/appearance.ts` gains `AUTOMATIC` with `resolveTheme` and an OS media-query watch; `index.html`'s pre-paint block resolves Automatic too, so following the OS is applied before the first paint. `i18n/index.ts` gains `loadExtraLocales`, merging locale files dropped into the data directory over the built-in strings and listing them by their own `language.name`.

## v0.62.0 delta

`ui/workspace-layout.ts` carries a slot map (`slots` per pane, `front` per slot): panes live in the left, right or bottom slot, a slot holding more than one stacks behind a `.pane-stack-tabs` strip positioned like the dividers, and hidden members stay in the DOM so node identity survives a move. The layout persists per interface profile at `formcut.layout.[profile]`, falling back to the older single key.
