---
name: mcp-workflows
description: "Do real work in formcut through its MCP tools: assemble a cut from local files and render it, make precise edits with raw commands, and build a rough cut from detected scenes, with the recovery steps for stale revisions, failed renders and interrupted jobs."
---

# MCP Workflows

## Purpose

Turn a request like "cut these three clips together and give me an mp4" into the right sequence of tool calls, carrying each handle from the call that returns it to the call that needs it. The exact tool list, with parameters, limits and defaults, is `references/tools.md`; quote names from there, never from memory.

## Before any workflow

1. `formcut_status`. If it does not return a version, stop and load `../mcp-setup/SUB-SKILL.md`.
2. Paths are on the machine running the engine, and must be absolute. A path from the user's own machine is only valid if the engine runs there too.
3. Keep a running note of every id and revision returned. The server remembers nothing.

## Workflow 1: assemble a cut and render it

Trigger: "put these files together", "make a video from these clips", "export this as an mp4".

1. `formcut_import_media` with `path`, once per file. Each returns a media id, its kind and its duration. The file is copied into the library; the original is untouched.
2. `formcut_create_project` with `title`, and `width`, `height`, `fps` if the user named them (defaults 1920, 1080, 30). Returns the project id and its first revision.
3. `formcut_add_clip` for each clip, in order: `project_id`, the `revision` returned by the previous call, `media_id`, `start` on the timeline in seconds, `duration`, `track` (0 is the top track), and `source_in` to start partway into the source. Each call returns the revision the next one must carry. Place clips end to end by starting each where the previous one ends; a still image needs an explicit `duration`.
4. `formcut_get_project` to confirm the clips, the frame and the total duration match what was asked.
5. `formcut_render` with `project_id`, `file_format` (`mp4` or `webm`) and `quality` (`low`, `medium` or `high`). Returns a job id at once; rendering takes minutes.
6. `formcut_render_status` with the job id until it reports done, which carries the output path. Poll at a sensible interval, not in a tight loop. Report the path to the user.

## Workflow 2: precise edits with raw commands

Trigger: trimming, splitting, effects, keyframes, transitions, anything the named tools do not cover.

1. `formcut_get_project`: the current revision and the clip ids on each track. Commands address clips by id.
2. `formcut_capabilities`: the edit operation names and project properties the engine accepts. Build commands only from names listed here.
3. `formcut_catalogue` when the edit names an effect, transition or blend mode: `kind` is `video`, `audio`, `transitions`, `blendModes` or `all`, and `group` narrows it (for example Blur, Adjust or Voice). Use the ids it returns.
4. `formcut_edit` with `project_id`, `revision` and `commands_json`: a JSON array of commands, for example `[{"op": "clip.split", "clipId": "abc", "time": 2.0}]`. Send related changes in one call so they land at one revision.
5. `formcut_get_project` again to confirm the result.

## Workflow 3: a rough cut from detected scenes

Trigger: "split this recording into its shots", "keep the best moments", "cut out the dead air between scenes".

1. `formcut_import_media` for the long recording, if it is not already in `formcut_list_media`.
2. `formcut_find_scenes` with `media_id` and `sensitivity` from 0 to 1 (default 0.5; higher finds more cuts). It returns each cut's time and the segments between them, and changes nothing.
3. Choose segments with the user, then build the cut: `formcut_create_project`, and one `formcut_add_clip` per kept segment, with `source_in` at the segment's start and `duration` its length, placed end to end on the timeline. To cut an existing clip at the scene times instead, use `formcut_edit` with `clip.split` commands.
4. Render as in workflow 1, steps 5 and 6.

For large or awkwardly encoded footage, `formcut_media_proxy` with `build` true makes previewing fast. Exports always read the original, so a proxy never lowers render quality.

## Workflow 4: make an effect package

Trigger: "make a look", "create a filter", "design a preset", "a vintage film effect I can reuse", "add an effect package".

A video package is a stack of formcut's own effects and grades, run by the same renderer as everything else, so it previews and exports alike and needs no code. Audio packages are filter chains added through the interface as a .zip; the tools here add video packages.

1. `formcut_package_guide`: the manifest format, every effect id with its parameters and ranges, and every grade setting with its range. Pass `group` (Blur, Stylize, Distort or Texture) to list one group in full. Use only ids, parameter names and values it lists.
2. Design the stack, usually a grade first and a finish after it:
   - A `grade` step sets the colour: temperature and tint for warmth, lift and contrast for the tone, saturation, per-channel shadows and highlights for split toning, sepia. Settings not named stay neutral.
   - Then one to three effect steps for texture: grain, vignette, light-leak, dust, halftone and the rest, each with an `amount` from 0 to 1 and `params` for its controls. Amounts from 0.3 to 0.8 read as a finish; 1 is the full effect.
   - Every step costs render time on every frame. Four steps is plenty; the heavier effects (oil-paint, crt-screen, clarity, lens-flare, stained-glass) are best alone.
   - Give it a lowercase id with hyphens, a name, and a `category` to group it in the browser. `names` can carry the name in each interface language.
3. `formcut_add_package` with the manifest. A refusal names the exact problem, such as a setting a grade does not have or a value outside its range; fix that and add again.
4. `formcut_preview_package` with its id: the rendered picture, as the effects browser shows it. Judge it; to refine, change the stack and add again with the same id, which replaces it.
5. Use it like any effect: its id is in `formcut_catalogue` (group Packages), and workflow 2 applies it to a clip with `formcut_edit`.

`formcut_list_packages` lists what has been added and any that failed to load. `formcut_remove_package` deletes one; formcut's own looks cannot be removed, and a package a saved project uses is refused with the projects' names, since they would not load without it.

## When something goes wrong

- **Stale revision.** The edit is refused and the reply carries the current revision. Call `formcut_get_project`, rebuild the command against what the project now contains (someone, or another agent, changed it), and retry once. Never retry with a guessed revision.
- **Engine not answering.** The reply names the address it tried. Stop and load `../mcp-setup/SUB-SKILL.md`; nothing in a workflow fixes a stopped engine.
- **A tool name does not resolve.** Compare with the host's listing and `references/tools.md`. There is no tool for a verb the list does not have; use `formcut_edit` with an operation from `formcut_capabilities`.
- **A package refused.** The reply names the step and the setting. Correct that one thing against `formcut_package_guide` and add again; do not guess other keys.
- **An edit refused as invalid.** Call `formcut_capabilities` and correct the operation name or property; do not invent operation names.
- **A render fails or is cancelled.** `formcut_render_status` gives the reason. Fix the cause it names, then call `formcut_render` again; `formcut_cancel_render` stops a render that is no longer wanted, and discards its partial output.
- **An interrupted, half-finished job.** Do not start over. `formcut_list_projects` and `formcut_get_project` show what already exists; `formcut_list_media` shows what was imported. Continue from the last step that landed, so nothing is imported or added twice.

## Is it the tools or this skill

When a step fails, call that tool directly, with this skill not loaded. If the direct call also fails, the fault is in the server or the engine, and no change to this skill fixes it: record it as such and load `../mcp-setup/SUB-SKILL.md`.

## Gate

The user has the output path from `formcut_render_status`, or a named, reported reason why not, and every id and revision used came from a tool's reply.
