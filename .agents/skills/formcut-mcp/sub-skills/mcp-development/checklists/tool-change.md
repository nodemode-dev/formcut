# Tool change checklist

Run for every added, renamed, removed or changed tool.

**The server**

- [ ] The tool follows the design rules in `../SUB-SKILL.md`: a workflow verb, explicit handles returned, revision taken and returned for edits, failures returned as text.
- [ ] Its description names only tools that exist, and says which tool uses its result next.
- [ ] If the typical order of calls changed, the `instructions` given to `MCPServer` at the top of `mcp/formcut_mcp.py` say so.

**Everything that names the tools**

- [ ] `README.md`, the MCP server section: the tool count and the list of names.
- [ ] `../../mcp-workflows/references/tools.md` in this pack: regenerate it with `python setup/mcp_tool_reference.py`, never by hand, so names, limits and defaults match exactly.
- [ ] The workflows in `../../mcp-workflows/SUB-SKILL.md`, if a tool they use changed.
- [ ] formcut.studio: `mcp_tools` in its `frontend/src/site/facts.json`, the count the site shows.

**Checks**

- [ ] `python -m pytest tests -q`, including `tests/test_mcp_tools_documented.py`.
- [ ] `ruff check backend/app mcp setup tests` and `ruff format --check backend/app mcp setup tests`.
- [ ] Called from a host with the engine running (`./formcut`): the tool appears in the listing, and a real call returns the handles the next step needs.
