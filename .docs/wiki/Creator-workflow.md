# Creator workflow

Import media in Media, drag it to a track, then select a clip. The Creator panel under the inspector exposes speed curves, motion presets, visual effects, audio processing, transitions, cutout and advanced assets. Preview and Export use the shared backend renderer.

Choose a speed preset, then edit individual time/rate points. The curve expresses source speed over timeline time; changing it does not automatically change the clip's timeline duration. Use trim to choose duration. A motion preset creates ordinary editable keyframes.

Visual/audio stacks process top to bottom. Each has an amount control; supported visual parameters appear below the stack. Audio volume ranges from zero to four; pan ranges from left to right. Detach audio creates an audio clip preserving timing, then mutes the source video.

Upload a .cube LUT or .wgsl shader under Advanced. Examples are provided in `examples/`. WGSL uses group 0 bindings: 0 is read-only storage array<vec4<f32>> input RGBA, 1 is read-only storage array<f32> containing width, height, time and zero, and 2 is writable storage array<vec4<f32>> output. Entry point `main` uses workgroup_size(64). Index bounds are the shader author's responsibility. Compilation is checked on import.

Expressions support t, duration, value, pi, arithmetic and sin/cos/tan/abs/min/max/sqrt/floor/ceil. They do not execute Python or JavaScript. Blank expression removes the override. Preview selection handles currently reflect keyframes rather than expression-driven geometry.

Open Studio > Local models to download or import the object/person segmentation models and Kokoro speech files. Downloads are explicit and cancellable. Object cutout uses U2NetP; person cutout uses U2Net human segmentation. In Creator > Cutout choose the model, set threshold and softness, then Enable cutout. Choose Restore or Erase and paint on preview. Strokes are saved in source coordinates. Remove last stroke or remove cutout to reverse edits.

The launcher (`./formcut`, `formcut.bat`) installs the speech runtime after the main install, idempotently, into an external Python environment in the data directory; `setup/setup_local_ai` or `setup/setup_local_ai.bat` re-runs that step alone. Install the Kokoro model and voices through Studio. Studio > Local speech generates audio into the bin and timeline. Text > Speak uses the same local engine for the selected title. The historical ElevenLabs API remains for compatibility, but those controls use Kokoro.

Studio > Stock media searches Pexels for video or photos with orientation, size and (for photos) colour filters and pages the results. Each card can add the item to the media bin, place it on a new track at the playhead, download the imported file, or open its Pexels page; the photographer credit and page URL are stored with the import.

Templates are full timeline documents. Studio > Templates can save the current document, export/import .fctemplate files, and bind each named media slot to available media. Duration fitting adjusts source rate. LUTs, shaders and imported fonts are embedded and remapped on import. Source footage is represented by slots, not embedded. Filled templates create an unsaved independent project.

Text can use an uploaded TTF/OTF font from the inspector. Use a font containing the script you intend to render; platform fallback cannot guarantee all glyphs. The interface is fully translated into twelve languages from one key table: 171 keys in each of English, Spanish and German, and 192 rows carrying the other nine.

## The effect browser

Effects, Filters and Transitions are driven by the engine catalogue rather than a
hardcoded list: 27 visual effects grouped as Blur, Stylize, Distort and Texture,
39 colour grades grouped as Adjust, Film, Warm, Cool and Split, 20 audio chains
as Voice, Tone, Space and Clean, two shape masks, two cutout models and all 12
transitions. Every card's thumbnail is a real render of the example image
through the same effect, mask or transition code the renderer uses, cached on
disk, so a card shows what the effect does. Clicking a card toggles that entry on
the selected clip's own stack; refusals say why (no selection, an audio chain on
a still, a cutout whose model is not installed).

## Timeline interaction

The playhead has a grab handle, and both it and the ruler scrub under pointer
capture: playback pauses, the position snaps to clip edges while the magnet is
on, and it always lands on a frame. Transcription appends captions to the track
named in the caption picker, and if that track already holds clips across the
caption span it creates a Captions track instead, so nothing is written over.

## Appearance and layout

Thirty appearance profiles live under Settings, Appearance: twenty-eight
palettes generated from one ladder table, plus two behaviours that pick a
palette (on every click, or every twenty seconds). The accent is separate and
free; a profile names a default and a chosen accent overrides it. A stored
profile and accent are applied before the first paint, so nothing flashes.

Panes resize by dragging the dividers between them, or from the keyboard with
arrow keys, Home and End once a divider has focus. The side panels can swap and
the timeline can sit above the panes; sizes and slots persist.

## Keyframes

Under the timeline, a lane per animatable property shows a diamond per keyframe.
Click empty lane to add one holding the value the clip already has, drag to move
it frame-snapped, alt-click to remove, double-click to cycle its easing. The
curve view shows one property as value over time with points draggable in both
axes, drawn with the renderer's own sampler, so the line is the animation. Its
eased-curves toggle (on by default) switches between that sampled line and
dashed straight segments between the keyframes. In the inspector, the scale,
position and rotation rows also carry a slider under the number field.

Track heights drag from a grip on the bottom edge of each track head (double
click resets). A work area on the ruler, created by a double press or with B
and N at the playhead, has a grip at each end; playback starts inside it and
loops back to its start, and double-clicking the bar clears it.

## Home screen

The home screen is a library: projects as cards, media as a searchable and
filterable grid with thumbnails, templates, local models and a storage
breakdown. Files dropped anywhere on it are imported. Media can be renamed,
revealed in the file manager and deleted from there; a rename changes the
library entry only, so a project's references cannot break.
