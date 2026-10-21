Read ../CLAUDE.md first, then ../.docs/wiki/Home.md for the subsystem map and the
contracts between parts. Licences are in ../.docs/wiki/Licences.md. This file is a pointer, not an installed
skill.

## Skills in this repository

`skills/formcut-skillset/` is the working knowledge of this codebase: a master
SKILL.md, six sub-skills under `sub-skills/`, and reference maps under each
sub-skill's `references/` folder derived from the tree rather than written from
memory. It validates clean against the skill format contract. Regenerate its
reference maps when the module or route inventory changes, and bump its
`formcut.version` metadata to the version it describes.

`skills/formcut-mcp/` is the other kind of work: driving formcut through its MCP
server rather than changing its code. `../.mcp.json` connects the server for
Claude Code in this checkout (`./formcut mcp`). `../.agents/skills/formcut-mcp`
is a generated mirror for Codex and other agents, briefed by `../AGENTS.md`;
`./formcut agents sync` regenerates the tool reference and the mirror, and
`./formcut agents sync --check` fails while they drift.
