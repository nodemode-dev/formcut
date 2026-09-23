# Effect packages

How formcut's data-defined effects work, for changing the code. An agent that only wants to make a package uses the MCP tools (formcut-mcp, workflow 4) or the interface's Import package.

## What a package is

A folder with a `manifest.json` (`id`, `name`, `kind`, optional `category` and `names` per language) and one backend:

- **Video: a stack**, in the manifest. Up to `STACK_STEPS` (8) steps, each `{"effect": id, "amount", "params"}` naming a built-in effect or named grade, or `{"grade": {setting: value}, "amount"}` with settings from `GRADE_RANGES`. `apply_effects` expands a stack step by step through `process` and `grade`, with each effect's `EFFECT_DEFAULTS` filled in, so a package previews and exports like any effect.
- **Audio: `chain.txt`**, an ffmpeg filter template with `{slot}` parameters declared in the manifest; only `ALLOWED_FILTERS` may appear. This allowlist is the security boundary for chains.
- **Video `chain.txt` is refused**: nothing on the frame path renders it. `shader.wgsl` loads but is not applied by the frame path.

## Where it lives

| Piece | Place |
| --- | --- |
| Loader, checks, install, remove | `backend/app/effect_packages.py` (`load_package`, `_check_stack`, `install`, `remove`, `projects_using`) |
| Rendering a stack | `backend/app/pixel_effects.py`, `apply_effects` and `_stack_steps` |
| Catalogue entries, groups Looks and Packages | `backend/app/catalogue.py`, `package_entries`, listed by `catalogue()` |
| Routes | `backend/app/main.py`: `GET /api/packages`, `GET /api/packages/schema`, `POST /api/packages/import`, `DELETE /api/packages/{id}`, `POST /api/packages/reload` |
| Thumbnails | `backend/app/effect_previews.py`, `known` accepts stack ids |
| The 180 built-in looks | `backend/app/effect_library/` written by `setup/effect_library.py` from its recipes and `setup/effect_library_names.json`; never edit the manifests by hand; `--check` in tests |
| Interface | `frontend/src/ui/media-pane.ts`: Looks and Packages categories, Import package, remove on a card, `refreshPackages` |
| MCP | `backend/app/agent_mcp.py`: `formcut_package_guide`, `formcut_add_package`, `formcut_preview_package`, `formcut_list_packages`, `formcut_remove_package` |
| Tests | `tests/test_effect_library.py`, `tests/test_package_import.py` |

## Rules the loader holds

- The library loads first; a person's package cannot take a library id, and importing an existing own id replaces it.
- An upload is at most 4 MB; a zip's unpacked size is checked from its directory before anything is read; only `manifest.json`, `chain.txt` and `shader.wgsl` are taken, written under those names, so a zip cannot write elsewhere.
- Removal is refused while a saved project uses the package, because the document validator refuses unknown effect ids.

## Changing things

- **A new built-in look:** add a grade or finish to `setup/effect_library.py` (names in `effect_library_names.json`, all eleven languages), run it, commit the generated folders.
- **A new stack grade setting:** add it to `pixel_effects.grade`, then to `GRADE_RANGES`; the schema route and the guide follow.
- **A new effect parameter:** read it in the effect's branch of `process` with its old constant as the default, add it to `PARAM_SPECS` (unknown keys are dropped by `clamp_params`) and `EFFECT_DEFAULTS`, a label in `PARAM_LABELS` if the general name says too little, and the label in sixteen languages. `tests/test_effect_controls.py` fails any control that changes nothing.
