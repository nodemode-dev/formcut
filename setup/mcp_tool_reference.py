#!/usr/bin/env python3
"""Write the formcut-mcp skill pack's tool reference from the MCP server's source.

    python setup/mcp_tool_reference.py           # rewrite the reference
    python setup/mcp_tool_reference.py --check   # exit 1 if it is out of date

Every tool mcp/formcut_mcp.py declares, with its exact name, its parameters (limits
and defaults as the server enforces them) and whether it changes anything, read with
ast so the MCP SDK need not be installed. Agents quote names from the reference, so
it is generated, never edited by hand.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "mcp" / "formcut_mcp.py"
REFERENCE = ROOT / ".claude" / "skills" / "formcut-mcp" / "sub-skills" / "mcp-workflows" / "references" / "tools.md"


def tools() -> list[dict]:
    found = []
    for node in ast.parse(SERVER.read_text(encoding="utf-8")).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        deco = next((d for d in node.decorator_list if isinstance(d, ast.Call) and ast.unparse(d.func).endswith(".tool")), None)
        if deco is None:
            continue
        keywords = {k.arg: k.value for k in deco.keywords}
        annotations = ast.literal_eval(keywords["annotations"]) if "annotations" in keywords else {}
        arguments = node.args.args
        defaults = [None] * (len(arguments) - len(node.args.defaults)) + list(node.args.defaults)
        parameters = []
        for argument, default in zip(arguments, defaults, strict=True):
            text = ast.unparse(argument.annotation) if argument.annotation else ""
            kind = re.match(r"Annotated\[(\w+)", text)
            limits = re.findall(r"\b(ge|le|gt|lt)=([\d.]+)", text)
            entry = f"`{argument.arg}` {kind.group(1) if kind else ''}".strip()
            if limits:
                entry += " (" + ", ".join(f"{key} {value}" for key, value in limits) + ")"
            if default is not None:
                entry += f" = {ast.unparse(default)}"
            parameters.append(entry)
        found.append(
            {
                "name": ast.literal_eval(keywords["name"]),
                "description": " ".join(ast.literal_eval(keywords["description"]).split()),
                "parameters": "; ".join(parameters) or "none",
                "effect": "read only"
                if annotations.get("readOnlyHint")
                else ("destructive" if annotations.get("destructiveHint") else "changes state"),
            }
        )
    return found


def reference() -> str:
    listed = tools()
    lines = [
        "# formcut MCP tools",
        "",
        (
            "Generated from `mcp/formcut_mcp.py` by `setup/mcp_tool_reference.py`: every tool the server declares, "
            "with its exact name, its parameters (limits and defaults as the server enforces them) and whether it "
            "changes anything. Names are case sensitive. If a host's tool listing disagrees with this file, the "
            "listing is current and this file is stale."
        ),
        "",
        f"The server declares {len(listed)} tools.",
        "",
        "| Tool | Parameters | Effect | What it does |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| `{t['name']}` | {t['parameters']} | {t['effect']} | {t['description'].replace('|', '/')} |" for t in listed]
    return "\n".join(lines) + "\n"


def main() -> int:
    text = reference()
    if "--check" in sys.argv[1:]:
        current = REFERENCE.read_text(encoding="utf-8") if REFERENCE.is_file() else ""
        if current != text:
            print(f"{REFERENCE.relative_to(ROOT)} is out of date: run python setup/mcp_tool_reference.py")
            return 1
        print("the tool reference matches the server")
        return 0
    REFERENCE.write_text(text, encoding="utf-8")
    print(f"wrote {REFERENCE.relative_to(ROOT)}: {len(tools())} tools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
