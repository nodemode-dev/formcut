# Cutdowns: shorter spots cut from a longer master

Use for making :06, :15, :30 or similar spots from a finished master (a brand film, a promo, a long ad) with its
voice-over and music bed: choosing scripts, joining the mix, cutting picture to the words, and delivering spots that
pass QC. Learned on the owner's Posh cutdowns (three rounds, seven delivered spots). Every rule below is there because
breaking it failed a round.

## Editorial rules

- Complete sentences only. Never end a line on a word that runs on; never start one mid-thought.
- No opener that assumes the audience already knows the brand or the previous line ("Posh doesn't only..." opened a
  round-one spot with no setup; judge whether a line can stand first).
- Sync dialogue (a receptionist answering, a customer speaking) only where the spot sets it up.
- Joins sit in silences between sentences, a whole number of bars apart, so the groove never skips; the pause the
  join leaves must sound natural (the pause is fixed by the grid: next speech start minus last speech end minus the
  bars jumped).
- End on the music's button (its final chord), usually with the call to action as the last unit.
- Each shot once per spot; picture matches the words being said.
- Open on the sharpest frame (not a fly-in or a motion-blurred frame).
- The output rate comes from the footage's measured cadence; holds and still graphics get a slow push so no frame
  repeats.

## The workflow, tool by tool

1. Import the master and read it: `formcut_import_media`, then `formcut_transcribe` (small model) for sentences with
   times. Sentence times are reliable; word times are not cut points.
2. Scripts: `formcut_plan_cutdown` with the length lists ranked scripts, each with its exact source segments, the bars
   jumped at each join and the pause each leaves (whole sentences, bar-aligned joins outside speech, the call to action
   last, ending on the button, the length exact). Choose among them by the editorial rules above; the ranking is by
   natural pauses, not by meaning. To adjust a join by hand, `formcut_music` with `out_from` and `out_to` lists the
   bar-aligned joins from that out-point.
3. Build each spot's timeline: the mix on two alternating audio tracks (one per unit, 20 to 30 ms crossfades at the
   joins, a short fade at the end), picture cuts from the master muted on a video track, matched to the words.
4. `formcut_speech_check`: every audio cut safe. Move any unsafe cut into the pause it names.
5. `formcut_frame_check` at the delivery rate with `fix`: no clip repeats a frame (in-point shifts, 1 to 2% speed-ups,
   pushes on holds).
6. `formcut_render` with the delivery rate, `audio_bitrate` (256 is common) and `loudness` set to the master's
   integrated loudness (measure it with `formcut_qc` on the master), true peak -1.
7. `formcut_qc` on every render with the loudness target: `passed` true, zero exact and near-duplicate frames, the
   first frame as sharp as its shot, loudness within 1 LU. A failed check is fixed in the project and rendered again,
   never delivered.
8. Export the project as a `.fc` package for the round trip: File, Export package in the app, or
   `GET /api/projects/{id}/package` on the engine (no MCP tool exports a `.fc` yet).

## Not yet automated

- Editorial choice: `formcut_plan_cutdown` lists feasible scripts ranked by how natural the joins sound, not by
  whether they tell a story; on the Posh master all seven delivered scripts are among its 26 :15 and 140 :30, the
  :15 at ranks 2, 4, 7 and 18. Read them and choose.
- The downbeat: `formcut_music` reports the music's first beat as the downbeat; it is not detected from the audio.
  Joins need only the bar length, so they are unaffected.
- Soft transitions in the picture (dissolves, wipes): `formcut_find_scenes` finds hard cuts only. Check in-points by
  eye for dissolve ghosts.
