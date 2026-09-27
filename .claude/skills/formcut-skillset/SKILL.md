---
name: formcut-skillset
description: "Use for any work on formcut, the local video editor: its Python FastAPI engine, vanilla TypeScript interface, Tauri shell, JSON-RPC automation surface, orchestration event stream and MCP server. Carries the codebase as it stands: module and route maps, the state engine and its commands, the shared renderer, timeline and keyframe behaviour, appearance profiles and tokens, locale keys, and the invariants that explain most bugs. Trigger on formcut, formcut engine, render session, clip visuals, keyframe lanes, appearance profile, formcut MCP, orchestration session, project.edit, api/rpc, or any file under backend/app, frontend/src or src-tauri. Also for adding an engine endpoint, changing a pane, extending the automation or MCP tools, wiring an external orchestrator in, or reviewing a change against this project build discipline. Route through formcut-director unless the question is narrow and owned by one specialist."
license: Apache-2.0
metadata:
  formcut.version: "1.99.1"
  formcut.compiled: "2026-09-25"
---

# formcut skillset

Working knowledge of formcut as it stands at v1.99.1: what each part is, why it is shaped that way, and the rules a change has to satisfy. It exists so that local development, and later an orchestrator driving formcut from outside, can act on the codebase without rediscovering it.

The premise: formcut is small enough to read and structured enough that most mistakes come from not knowing an invariant rather than from writing bad code. One renderer serves preview and export, one engine owns document state, every colour is a token, every string is a key, and every automated caller goes through one JSON-RPC surface. Break one of those and the symptom appears somewhere else entirely, which is what this pack is written to prevent.

## Shape of the project

```
formcut/
  backend/app/        Python FastAPI engine, 78 modules, 172 routes, the MCP server (agent_mcp.py) among them
  frontend/src/       vanilla TypeScript interface: engine, ui, workers, i18n, styles
  src-tauri/          Tauri 2 desktop shell, spawns the engine as a sidecar
  mcp/                launcher that runs the engine's MCP server from a checkout (the app runs formcut-engine --mcp)
  setup/              install, boot, banner and build scripts
  .docs/wiki/         published subsystem documentation
  examples/demo/      the four demo files the demo project loads, tracked with their credits; anything else here stays local
```

## Routing: which sub-skill to load

Start at `sub-skills/formcut-director/SUB-SKILL.md` for anything broad or unscoped. Load a specialist directly only when the question is plainly inside it.

| If the work is about | Load this sub-skill |
| --- | --- |
| Anything unscoped, a new feature, a bug with no obvious owner, phase planning, or a change that crosses the engine and the interface | `formcut-director` |
| Engine modules, routes, jobs, rendering, decoding, export, media, models, providers, storage, speech | `engine-architect` |
| Interface modules, the state engine, panes, settings popout, appearance profiles and tokens, locale strings, home screen | `interface-architect` |
| Timeline behaviour, clips, keyframes and curves, waveforms and filmstrips, playback, audio scheduling, preview streaming | `timeline-and-render` |
| The JSON-RPC surface, orchestration sessions and events, the MCP server and its tools, an external system driving formcut | `orchestration-and-mcp` |
| Reviewing or making a change under this project's rules: surgical edits, stable DOM, tokens, versioned deliverables, verification bar | `build-discipline` |

## Invariants that explain most bugs

These are the load-bearing rules. Each one has a symptom that shows up far from its cause, which is why they are stated here rather than buried in a reference.

- **One renderer serves preview and export.** `backend/app/renderer.py` composites for both. A preview that differs from the exported file means a path bypassed it, not that the preview is approximate.
- **The interface engine owns the document.** `frontend/src/engine/project.ts` holds state, applies commands, pushes history and emits. UI modules subscribe and dispatch; nothing else mutates a project. It emits exactly five names: clips, playhead, transport, timeline, project, plus clip-selection. Listening for an invented name fails silently, which has happened twice in this codebase.
- **Every colour, radius, spacing and z value is a token.** `frontend/src/styles/tokens.css` defines them; 28 appearance profiles override them in `themes.css`. A hardcoded colour looks correct in the default profile and wrong in the other 27.
- **Every string is a locale key.** 962 keys in each of en, es and de, a generated pack of 1119 phrase rows carrying nine more locales, and four complete locale files (ar, fa, he, hr) under `frontend/public/locales`, loaded at start: sixteen languages, three of them right to left. An English literal in the interface is a defect, not a shortcut.
- **One automation surface.** `POST /api/rpc` is how anything outside the interface builds, edits, renders and collects. Adding a second path to change a project means two clamping rules and two history behaviours.
- **Jobs are handles, not waits.** Renders return a job id immediately; progress arrives by polling or on the orchestration event stream. A synchronous render is a request that times out.
- **Media files are named by id.** A library rename changes the entry, never the file, so a project's media references cannot break.

## Running it

```bash
cd backend && ./oc_install      # engine virtualenv
cd ../frontend && ./oc_install  # interface dependencies
cd .. && ./formcut              # banner, idempotent install, boot
```

The engine listens on 127.0.0.1:8040, the interface dev server on localhost:3040 with `/api` proxied. `./formcut` only sequences the three scripts in `setup/`. Keys live in `.env` beside the launcher, with `example.env` as the template, and the launchers export it before starting.

## Verification bar for any change here

This project's own rule, and the reason its build notes are worth reading: a claim that was not run is not a result. Before reporting work finished, state the numbers. Typechecks and builds pass, the affected flow was driven in a real browser or against the real engine, measurements are quoted rather than described, and anything that could not be verified is named as unverified. The `build-discipline` sub-skill carries the full ledger.

## Evaluations

Each names an observable behaviour, so a later change to this pack can be checked rather than admired.

1. **Asked to add an engine endpoint** (for example, one reporting decoder pool statistics), the response mounts it in the `features.py` tuple rather than appending an include inside the loop, and says which module owns it. Failure looks like a thirteen-times mount or a new module with no router prefix.
2. **Asked why a subscriber never fires**, the response checks the emitted names before reading the subscriber, and names the six the engine actually emits. Failure looks like debugging the render path first.
3. **Asked to add a control to a pane**, the response uses a token for every colour, adds a locale key in all sixteen locales, and reconciles rather than rebuilding the container. Failure looks like a hex value, an English literal, or an innerHTML assignment on a mounted pane.
4. **Asked to expose a new capability to an agent**, the response extends `POST /api/rpc` and then the MCP tool surface, rather than adding a second mutation path, and returns a handle instead of holding state.
5. **Asked whether a change is finished**, the response quotes numbers from a real run and names anything it could not verify, rather than describing the work as complete.

## Trigger test

Should load this pack: "the formcut preview is darker than the export"; "add a peaks endpoint to the engine"; "why does my inspector subscriber never run"; "extend the formcut MCP with a trim tool"; "add a Norwegian locale to formcut"; "wire an orchestrator into api/rpc".

Should not load it: "what is the best video codec for archival storage" (general knowledge, no formcut surface); "write an MCP server for my Jira instance" (MCP but not this project, load the MCP oracle); "build me a video editor" (a new project, not this codebase); "cut this footage for me" (a request for editing work, not for changing formcut).

Near misses worth getting right: "my Tauri sidecar will not start" loads this pack only if the project is formcut, otherwise it is a Tauri question; "add a theme to nodemode" is the sibling project's styling, not this one.
