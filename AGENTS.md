# formcut

A local video editor in the form family beside formvfx and formvis: a vanilla TypeScript and Vite interface, a Python FastAPI engine, and a Tauri 2 desktop shell.

## Editing video (natural language)

When the person wants a video cut, assembled, captioned or rendered in formcut, use the `formcut` MCP server's tools guided by the `formcut-mcp` skill in `.agents/skills/formcut-mcp` (its `sub-skills/mcp-workflows/references/tools.md` lists every tool). Start with `formcut_status`, import with `formcut_import_media`, build with `formcut_create_project` and `formcut_add_clip`, change with `formcut_edit` carrying the last revision, and render with `formcut_render` then `formcut_render_status`.

The MCP server is configured here in `.codex/config.toml` (Codex) and `.cursor/mcp.json` (Cursor); both run `./formcut mcp`, which starts the engine when nothing answers. From any other folder, `./formcut agents install` sets Claude Code, Codex and Cursor up for the user account. Without MCP, `POST /api/rpc` on the engine (127.0.0.1:8040) is the same surface.

## Changing formcut's code

Read `CLAUDE.md` and `.claude/skills/formcut-skillset/SKILL.md` (route through its `formcut-director` sub-skill), then the wiki page for the area under `.docs/wiki/`. After changing MCP tools, run `./formcut agents sync`.
