---
name: mcp-director
description: "Entrypoint for any formcut MCP request. Decides whether the job is setup, work or development, loads that sub-skill, and checks the engine and the connection before any work starts."
---

# MCP Director

## Purpose

Route a formcut MCP request to the right specialist, and make sure the ground is solid before work begins: an agent that starts importing media into an engine that is not running wastes every call after the first.

## Procedure

### 1. Classify the request

| Signal in the request | Route to |
| --- | --- |
| install, register, config, host, cannot see the tools, not answering, FORMCUT_ENGINE | `../mcp-setup/SUB-SKILL.md` |
| cutdowns: :06, :15 or :30 spots cut from a longer master, versions of an ad, bar-aligned joins, delivery QC | `../cutdown/SUB-SKILL.md` |
| make, cut, assemble, edit, trim, add effects, find scenes, render, export, where is my file | `../mcp-workflows/SUB-SKILL.md` |
| make or design a look, filter, preset or effect package; list or remove packages | `../mcp-workflows/SUB-SKILL.md` (workflow 4) |
| add a tool, change a tool, rename, parameter, SDK, formcut_mcp.py itself | `../mcp-development/SUB-SKILL.md` |

A request can span two. Setup always comes first: if the tools are not reachable, no workflow can run.

### 2. Check the ground before any workflow

Call `formcut_status` first. It reports the engine's version, how many projects and media items it holds, and what the effect catalogue offers. If it returns text saying the engine is not answering, stop and hand over to setup; do not attempt the workflow.

### 3. Keep the handles visible

Write down each id and revision as it is returned. The server remembers nothing, so the conversation is the only place the chain of handles lives. When a multi-step job is interrupted, these notes are what make it resumable.

## Gate

The right specialist is loaded, `formcut_status` has answered when work is about to run, and the handles returned so far are written down.
