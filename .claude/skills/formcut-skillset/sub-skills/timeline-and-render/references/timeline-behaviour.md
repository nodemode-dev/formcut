# Timeline behaviour

## Interaction

- The playhead carries a grab handle; it and the ruler scrub under pointer
  capture. Playback pauses on grab, the value snaps to clip edges while the
  magnet is on, and it always lands on a frame.
- Snapping for scrubbing builds its own edge list. Reusing the clip-drag snap
  helper broke it, because that helper includes the playhead and the playhead
  sits on the edge it just snapped to.
- Dividers between panes are absolutely positioned over the grid gaps, not grid
  tracks, so the template stays the three panes it always was. Sizes are pixels
  clamped to a 240 px floor and 45 percent of the workspace.
- The timeline chip opens a menu of three heights, 25, 42 and 65 percent of the
  workspace; the row divider sets any height from 15 to 80 percent.

## Stacking and scroll

- One z-scale in `styles/tokens.css`, in steps of 100: base, clips, handles,
  ruler, playhead, sticky heads, dropdowns, overlays, toasts. No other file
  writes a z-index number.
- The ruler and its corner cell stick to the top and the track heads to the
  left, so they stay put while the lanes scroll under them.
- The playhead lives inside the grid in content coordinates, so it scrolls with
  the lanes and needs no scroll listener to follow them.

## Keyframes

- `ui/track-keyframes.ts` opens a block under a track from the toggle in its
  head: a sticky head cell with the property labels and a body cell on the
  timeline's own axis, so diamonds share the clips' time scale and scroll.
  The body shows lanes or curves.
- Zoom reaches the block through the `data-scale` attribute, which the module
  watches; the timeline pane only installs it.
- Drags listen on the window, because each dispatch repaints the diamonds and
  a captured element can be replaced mid-drag. A click on a lane adds a key,
  Alt-click removes one and a double-click cycles its easing.
- Rows are separated by inset box shadows rather than borders, so no row or
  diamond moves by a pixel.

## Drawing

- `ui/clip-visuals.ts` paints a canvas inside each clip body, created once and
  repainted in place, skipped unless a signature (media, kind, geometry, source
  in, duration, speed, curve) moved.
- Waveforms come from `/api/media/{id}/peaks`: 2000 buckets of min and max at
  8 kHz mono, rounded to three decimals. Filmstrips come from
  `/api/media/{id}/filmstrip?frames=N`: one row of N equal frames, so the
  geometry is exact rather than inferred from the aspect ratio.

## Playback numbers measured on one CPU core under 4x throttling

- Graded overlay preview frame: 27 ms, from 491 ms before the still cache.
- Music video segment: 8 fps with 0.36 s lag.
- Audio: 12.5 s of continuous playback, worst drift 22 ms, ratio 1.000.
- Full demo export at 1080p: 160.4 s.
- 4K HEVC real-time playback: decode bound here, unverified on multi-core.

## Track heights, track state and the work area (v0.54.0)

- Each track head and its lane read one custom property, `--track-h`, written
  by `ui/track-height.ts` from a grip on the head's bottom edge: 32 to 240 px,
  default 56, double-click resets, persisted per track index in
  `formcut.trackHeights`. The keyframe block under a track is not part of that
  height; it has its own rows.
- Hidden and muted heads swap glyphs (`eye` to `eyeOff`, `speaker` to `mute`)
  and take `.is-off`; locked keeps `.is-accent`. The override lives under
  `.track-head .iconbtn` because that rule sits later in `app.css` at equal
  specificity and used to silence both states: a track could be hidden with
  nothing on the head to say so.
- The work area (`ui/work-area.ts`) is a bar along the bottom of the ruler
  with a grip at each end. A double press on the ruler creates one around that
  point (detected on the pane in the capture phase, because the first press
  scrubs the playhead under the cursor and the second lands on the playhead
  grab, not the ruler), B and N set in and out at the playhead, the bar drags
  as a whole, double-click on it clears it. It is engine state outside the
  document (`engine.workArea`, `setWorkArea`): `play()` starts inside it and
  wraps to its start at its end. Persisted per project id in
  `formcut.workArea`.
- The keyframe graph's curves toggle (`formcut.kfCurves`, default on) draws
  the sampled eased path when on and dashed straight segments between the
  keyframes when off; the disclosure on each head shows a diamond.
