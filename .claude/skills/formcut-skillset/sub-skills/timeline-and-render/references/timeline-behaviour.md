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
