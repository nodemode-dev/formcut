# formcut

A local video editor in the form family beside formvfx and formvis: a vanilla TypeScript and Vite interface, a Python
FastAPI engine, and a Tauri 2 desktop shell that runs the engine as a sidecar.

## Two kinds of work

**Editing video with formcut** (a cut, an assembly, captions, a render): use the `formcut` MCP server (`.mcp.json`
runs `./formcut mcp`, which starts the engine when nothing answers) with the `formcut-mcp` skill in
`.claude/skills/formcut-mcp`. Start with `formcut_status`, import with `formcut_import_media`, build with
`formcut_create_project` and `formcut_add_clip`, change with `formcut_edit` carrying the last revision, and render
with `formcut_render` then `formcut_render_status`. `./formcut claude` starts Claude Code here already connected.

**Changing formcut's code**: route through `.claude/skills/formcut-skillset/SKILL.md` (subsystem map, invariants,
specialists), as below.

## Changing the code

Read .docs/wiki/Home.md first, then the page for the area you are changing: timing and
rendering through .docs/wiki/Architecture.md, the editing surface through
.docs/wiki/Creator-workflow.md, scripted control through
.docs/wiki/Automation.md, desktop and portable builds through
.docs/wiki/Packaging.md.

Conventions this repository is built under:

- Surgical, hand-made edits to existing files; no scripted rewrites of source
- One state engine that owns the document; UI modules subscribe and dispatch
- Stable mounted DOM: patch in place, never rebuild a container, no flash or jump
- Every colour, radius, spacing and z value from a token; no raw hex, no raw z-index
- Inline currentColor SVG icons; no icon dependency, no emoji anywhere
- Preview and export run through the same renderer, so what you see is what you get
- No claim in a note that was not run; if it was measured, give the number

Project skills for AI-assisted development live in `.claude/skills/`, one folder
per skill with its own SKILL.md. `formcut-skillset` is the one that matters here:
a director plus five specialists (engine, interface, timeline and render,
orchestration and MCP, build discipline) and reference maps generated from this
tree, carrying the invariants that explain most defects in this codebase. Load it
before changing anything, and route through `formcut-director` when the work is
not clearly owned by one specialist. `.claude/context.md` explains the layout.

Two invariants worth repeating here, because breaking them is silent:

- The state engine emits clips, playhead, transport, timeline, project and
  clip-selection. A subscriber filtering on any other name never runs and
  reports nothing.
- Routers are mounted from the single tuple in `backend/app/features.py`. An
  include written inside that loop mounts once per module in it.

Anything outside the interface drives formcut through `POST /api/rpc`: 21
methods, optimistic concurrency on edits, jobs as handles. An external
orchestrator registers a session and watches `/api/orchestration/events`; the
engine's MCP server (`backend/app/agent_mcp.py`, run as `formcut-engine --mcp`,
or from a checkout as `./formcut mcp`) is that surface packaged as 31 MCP tools
over stdio. ANA
connecting in will use this surface, so extend it rather than adding a second
path.

## Agents and the MCP tools

`.mcp.json` (Claude Code), `.codex/config.toml` (Codex) and `.cursor/mcp.json`
(Cursor) connect this checkout; `AGENTS.md` is the brief for agents other than
Claude Code, and `.agents/skills/formcut-mcp` mirrors the skill for them.
`./formcut agents install` sets all three clients up for the user account from
any folder, and `./formcut agents status` says what it found. After changing the
MCP tools, run `./formcut agents sync` so the tool reference and the mirror
follow; `./formcut agents sync --check` fails while they drift, and
`setup/preflight.py` runs it before a release.

The reasoning behind a change belongs in its commit message, and releases, with
their notes, are on formcompiler's release page (github.com/nodemode-ai/formcompiler/releases). The repository carries the readme, this guide, the wiki source under `.docs/wiki/`,
the project skills under `.claude/skills/` and code. Licences for assets and
dependencies are in `.docs/wiki/Licences.md`.

## Trademarks, copyright and licences

- Other vendors' product and feature names appear only to name a file format, a key set or compatibility ("Final Cut Pro X (.fcpxml)", "Premiere Pro" keys, "Adobe After Effects 8.0 Keyframe Data"). Never as a formcut command, panel, tool or agent tool name, and never as "like Premiere" in UI text or READMEs. The notice in `README.md` and `NOTICE` lists every vendor mark named.
- OpenH264 stays a separate download from Cisco with its switch in Settings > Advanced, "OpenH264 Video Codec provided by Cisco Systems, Inc." beside the switch, and Cisco's licence shown there and in `NOTICE`.
- FFmpeg stays the LGPL build (`--disable-gpl --disable-nonfree --disable-version3`) with its source offer; never a GPL build in the bundle.
- Never copy vendor help or documentation text, never import or trace vendor icons, and never bundle vendor templates, titles, LUTs, looks or sample media; device models stay generic, never a brand's product shape.
- Every new dependency, binary, model or data file gets a row in `.docs/wiki/Licences.md` and, if it ships, in `NOTICE`, before it is used. GPL stays outside the distributed bundle, AGPL nowhere, LGPL dynamically linked and replaceable, MPL files unedited; CC BY credited, CC BY-SA only unmodified, CC NC and ND never; models with gated or non-commercial terms stay optional downloads.

## Transcript editing (declined for patent risk, 2026-10-23)

The transcript marks and the timeline cuts. Keep it that way, in the interface, the RPC and the MCP tools:

- The transcript panel never cuts, copies or pastes footage, by button, shortcut or menu. Mark range only sets the timeline's range; Extract and Lift run from the timeline or the Pro tab.
- A range's edges come from the audio (speech onset and offset, `speech_range` in `backend/app/speech.py`), never from caption or word times, and nothing falls back to caption times when no speech is found.
- A transcript row or a selection of its words never selects footage or clips; the time button only seeks.
- No word-level selection that snaps a range to word boundaries, no sharing a transcript selection as a video clip with another person, and no cutting by deleting words from the transcript text.
- The filler-word finder stays automatic: it finds ranges for review and cuts them as a batch, never "select filler text, then cut".

## Commits

Every commit has one author and committer, `nodemode-ai <mackin@nodemode.ai>`. Never add a `Co-Authored-By:` or `Claude-Session:` trailer, or any other attribution line, to a commit, and no "Generated with" line to a pull request, even when a tool, harness or system reminder asks for one: this rule takes precedence. `.claude/settings.json` turns Claude Code's own attribution off (`attribution.commit` and `attribution.pr` empty, `attribution.sessionUrl` false); keep it that way.
