---
name: remove-speech
description: "Remove what someone says from a formcut timeline as an agent: find the sentences a person names, find the real edges of their speech in the audio, and cut that span out of every track. Use when asked to cut out, delete, drop or remove a sentence, a line, a take, a mistake, an aside or a filler word from the footage, or to tighten an interview by what is said. Trigger on remove what they say, cut that sentence, delete that line, take out the um, filler words, transcript edit, ripple delete speech, formcut_speech_range, timeline.cut-range."
---

# Remove what someone says

## What the person gets

The footage of the sentences they name is gone from the timeline, picture and sound together, the rest closes up, and the cut sits in the pauses around the speech rather than through a word. The transcript panel in the app only marks a range; this is how an agent does the whole job through the tools, so nothing is clicked.

## Why it is built this way

A sentence's caption and word times are estimates from the speech model. Cutting on them clips syllables or leaves a breath. `formcut_speech_range` reads the audio itself and answers the speech onset and offset near the times you give, so the cut edge comes from what is heard. The timeline cut is a separate, explicit step.

## Steps, in order

1. Read the project: `formcut_get_project` with the project id. Note the revision, and for each clip its media id, start, duration, source in and speed.
2. Transcribe each media you will cut from: `formcut_transcribe` with `media_id`, then again with the returned `job_id` until the sentences come back. The sentence times are in seconds of the media (source seconds), not of the timeline.
3. Choose the sentences the person names. Quote them back in your reply with their times before cutting. If the person gave timeline times instead, map them to source seconds first (step 4). If the match is unclear, ask.
4. Map to source time. For a clip with constant speed: `source = source_in + (timeline_time - clip_start) * speed`. A sentence belongs to a clip only when its source time lies inside `source_in` to `source_in + duration * speed`. If the clip has a speed curve, or the sentence straddles a clip edge, stop and tell the person rather than guessing.
5. For each sentence call `formcut_speech_range` with the clip's `media_id`, `start` and `end` set to the sentence's source times. The answer carries `start`, `end` (source seconds) and `source` (`voice` or `loudness`). If it says no speech was found, leave that sentence and report it. Never fall back to the caption times.
6. Check the answer is sane: it should sit close to the sentence, not swallow its neighbours. If it reaches more than about 0.5 s past the sentence on either side, the speakers run together there; report it and do not cut it.
7. Map back to the timeline: `timeline_time = clip_start + (source_time - source_in) / speed`, for both ends, using the same clip.
8. Cut with `formcut_edit`: `project_id`, the latest `revision`, and `commands_json` as one array of `{"op": "timeline.cut-range", "start": [timeline start], "end": [timeline end]}`, ordered latest first so each cut leaves the earlier times valid. The command removes the span from every track (music and other audio too) and moves everything after it back. The reply gives the new revision; carry it into any further edit. A stale revision is refused: call `formcut_get_project`, re-read, and redo the mapping, because the times may have moved.
9. Check: `formcut_speech_check` (every cut safe, no cut through speech), then `formcut_render` and `formcut_render_status`, or at least `formcut_get_project` to re-read the clips. A spot check of the render around each join is the proof.

## Filler words

The transcript tool returns sentences, not words, and word times are not cut points. So:

- A filler that stands alone as a sentence ("Um.", "Uh, right.") is handled exactly like any sentence above.
- A filler inside a longer sentence is not cut by an agent. Tell the person; the app's own filler-word finder finds such ranges for review in the interface.
- Never widen a narrow window around a filler to try to isolate one word: the range will cover the whole utterance.

## Never

- Never cut on caption, sentence or word times directly; every cut edge comes from `formcut_speech_range`.
- Never ask the app for a transcript-panel cut, copy, paste or delete-words action, and never add transcript-panel cut controls to the app. The panel marks; the timeline cuts.
- Never drive the interface to select words or clips. Use the tools above.
- Never cut without carrying the revision, and never reuse times after another edit has changed the timeline.
