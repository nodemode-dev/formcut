---
name: formcut-mcp
description: "Drive, connect and extend formcut's MCP server (28 formcut_* tools over stdio, built into the app as formcut-engine --mcp, driving the formcut that is running). Use whenever an agent should build, edit, render or collect a formcut video project through MCP; when connecting it to Claude Code, Codex, Cursor, Claude Desktop, VS Code or another MCP client; when a formcut tool call fails, the engine is not answering, the tools do not show up, or an edit is refused for a stale revision; or when adding, renaming or changing a formcut MCP tool. Trigger on formcut MCP, formcut_mcp.py, formcut_status, formcut_add_clip, formcut_edit, formcut_render, render a formcut project from an agent, cut or assemble a video with MCP, rough cut by scenes, connect formcut to Claude, Codex or Cursor, formcut-engine --mcp, engine.json, FORMCUT_ENGINE, or stale revision, even when MCP is not named. Route through the mcp-director sub-skill by default."
license: Apache-2.0
---

# formcut MCP

formcut's MCP server puts the editor in front of an agent. It is one Python module, `backend/app/agent_mcp.py`, exposing 28 workflow-shaped tools over stdio; the installed app runs it as `formcut-engine --mcp`, and it talks to the running formcut engine over HTTP. This pack is the knowledge layer over it: how to connect it, how to get real work done with it, and how to change it without breaking the agents that depend on it.

The server gives access; it does not give judgment about order, preconditions or recovery. That is what these sub-skills carry.

## Facts every sub-skill relies on

- The server is stateless. Every call returns the handles the next one needs (project id, media id, job id, revision); nothing is remembered between calls, so a dropped connection loses no state.
- Edits use optimistic concurrency. Every edit carries the revision the agent last saw and returns the new one. A stale revision is refused with the current revision, and the fix is to re-read the project and retry, never to guess a number.
- Errors are results, not exceptions. A failed call returns text naming the recovery step. Read it and act on it.
- The server finds the formcut that is running on every call: `FORMCUT_ENGINE` if set, else the address the app publishes in `engine.json` in its data folder, else `http://127.0.0.1:8040`, where `./formcut` starts a source run. Installed or from source, an agent drives the app a person sees.
- Tool names are case sensitive and are quoted in this pack exactly as the server declares them. The current listing is in `sub-skills/mcp-workflows/references/tools.md`; when the server and that file disagree, the server wins and the file is stale.

## Routing

Start with `sub-skills/mcp-director/SUB-SKILL.md` for anything broad; it decides which of the four below applies. Load one directly for a narrow question.

| The request is about | Load |
| --- | --- |
| Installing the server, registering it with a host, environment variables, the tools not appearing, the engine not answering | `sub-skills/mcp-setup/SUB-SKILL.md` |
| Doing work: importing media, building a timeline, raw edits, scene detection, rendering and collecting the file, recovering a half-finished job | `sub-skills/mcp-workflows/SUB-SKILL.md` |
| Changing the server: a new tool, a renamed or removed tool, a changed parameter, the SDK version, keeping docs and counts in sync | `sub-skills/mcp-development/SUB-SKILL.md` |
| Cutting shorter spots (:15, :30) from a master: scripts, bar-aligned joins, speech-safe cuts, frame and loudness QC | `sub-skills/cutdown/SUB-SKILL.md` |

## Evaluations

`EVALS.json` holds the evaluations this pack is checked against: realistic requests with observable expected behaviour, including one where the pack must not overreach.
