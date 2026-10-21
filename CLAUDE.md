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
their notes, are on the GitHub Releases page. The repository carries the readme, this guide, the wiki source under `.docs/wiki/`,
the project skills under `.claude/skills/` and code. Licences for assets and
dependencies are in `.docs/wiki/Licences.md`.
