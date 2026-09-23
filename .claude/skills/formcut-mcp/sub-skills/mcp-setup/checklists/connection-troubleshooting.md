# Connection troubleshooting

Work in order and stop at the first step that fails.

**1. Is the server connected to the host**

- [ ] The host lists `formcut` (Claude Code: `claude mcp list`; Claude Desktop: the tools menu), and it reads as connected, not only configured.
- [ ] If it fails to start: run the registered command by hand. `ModuleNotFoundError: mcp` or `cannot import name MCPServer` means `mcp/.venv` is missing or holds an SDK older than 2.2: rerun `mcp/oc_install`.

**2. Is the engine answering**

- [ ] `formcut_status` returns a version. If it says the engine is not answering at an address, start the engine with `./formcut` in the checkout, or set `FORMCUT_ENGINE` to where it listens.
- [ ] The engine is a source run or an engine at a known address, not the desktop app, whose port is random.
- [ ] A timeout on a long call: raise `FORMCUT_MCP_TIMEOUT`, or poll a render with `formcut_render_status` instead of waiting on one call.

**3. Is it the server or the skill**

- [ ] Call the failing tool directly, with this skill not loaded. If that also fails, the problem is the server or the engine, and no change to the skill fixes it. Record it as a server fault.

**4. Are the tool names right**

- [ ] The name used matches the host's current tool listing exactly; names are case sensitive and all start with `formcut_`.
- [ ] If a tool is missing from the listing, the server may be older or newer than this pack: compare with `../../mcp-workflows/references/tools.md` and trust the listing.
