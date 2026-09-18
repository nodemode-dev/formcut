---
name: timeline-and-render
description: >-
  Timeline interaction, preview streaming, scheduled audio, clip waveforms and filmstrips, and the keyframe lanes and curve editor.
---

# timeline and render

Timeline behaviour, playback and what clips draw. Load `references/timeline-behaviour.md` for the interaction and drawing details.

## Playback

Playing streams JPEG frames from a dedicated renderer over `/api/render/sessions/{id}/stream`, paced to the wall clock from the moment the request arrives, with catch-up capped below the decoder's forward-skip window. Paused and scrubbed frames come from the lossless PNG frame endpoint, so a still matches export exactly.

Audio is scheduled, not synced. The mix renders only when the audio signature changes (clip media, timing, speed, volume, mute, fades, audio effects, track mute, active timeline, duration), is decoded once into an AudioBuffer, and is started from the playhead with a 60 ms lead. The module reports its own position and registers as the engine's clock source. A seek is a restart; a seek is detected as a divergence between the playhead and the audio position, because the state engine emits no seek event.

## Clips

Audio clips draw their envelope from `/api/media/{id}/peaks`; video and image clips draw frames from `/api/media/{id}/filmstrip`. Both endpoints describe whole media, and the interface windows them, so trimming or zooming slices a cached whole. Column to source time resolves through the engine's own speed mapping, so a retimed clip shows what it will really play. The waveform normalises to the loudest point in view, with the gain capped, because absolute level in a 26 px lane is accurate and unreadable.

## Keyframes

Five animatable properties (posX, posY, scale, rotation, opacity) and five interpolation modes (linear, ease, easeIn, easeOut, hold). Lanes and the curve view are two views of the same data and edit through the commands that already exist: `clip.keyframe` to set or remove, `clip.interp` to cycle. A move is a remove and a set, because the engine has no move command. The curve is drawn with the engine's own sampler, so the line is the animation rather than a second implementation of easing.

Clicking empty lane adds a keyframe holding the value the clip already has at that time, so adding a point never changes the picture. The inspector samples the transform at the playhead when a clip has keyframes; reading the base transform instead made the fields disagree with both the lanes and the rendered frame.
