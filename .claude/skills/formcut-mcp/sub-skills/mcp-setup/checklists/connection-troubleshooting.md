# Connection troubleshooting

Work in order and stop at the first step that fails.

**1. Is the server connected to the host**

- [ ] The client lists `formcut` (Claude Code: `claude mcp list`; Codex: `codex mcp list`; Claude Desktop and Cursor: their tools list), and it reads as connected, not only configured.
- [ ] If it fails to start: run the registered command by hand, and copy it again from Settings, Connections, AI agents if the app has moved. From a checkout, `ModuleNotFoundError: mcp` means the virtualenv lacks the SDK: install `backend/requirements.txt`, or rerun `mcp/oc_install`.

**2. Is the engine answering**

- [ ] `formcut_status` returns a version and an address. If it says formcut is not running, open the formcut app (or start `./formcut` in a checkout) and call again; nothing needs restarting on the agent's side.
- [ ] If the app runs with a custom data folder, the server needs the same `FORMCUT_DATA_DIR` to find `engine.json`; or set `FORMCUT_ENGINE` to the address directly.
- [ ] A timeout on a long call: raise `FORMCUT_MCP_TIMEOUT`, or poll a render with `formcut_render_status` instead of waiting on one call.

**3. Is it the server or the skill**

- [ ] Call the failing tool directly, with this skill not loaded. If that also fails, the problem is the server or the engine, and no change to the skill fixes it. Record it as a server fault.

**4. Are the tool names right**

- [ ] The name used matches the host's current tool listing exactly; names are case sensitive and all start with `formcut_`.
- [ ] If a tool is missing from the listing, the server may be older or newer than this pack: compare with `../../mcp-workflows/references/tools.md` and trust the listing.
