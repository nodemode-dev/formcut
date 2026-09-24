# Working on formcut

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
or from a checkout through `mcp/`) is that surface packaged as 21 MCP tools
over stdio. ANA
connecting in will use this surface, so extend it rather than adding a second
path.

The reasoning behind a change belongs in its commit message, and releases, with
their notes, are on the GitHub Releases page. The repository carries the readme, this guide, the wiki source under `.docs/wiki/`,
the project skills under `.claude/skills/` and code. Licences for assets and
dependencies are in `.docs/wiki/Licences.md`.
