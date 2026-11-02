#!/usr/bin/env python3
"""Regenerate the inventory sections of the formcut-skillset reference maps.

    python setup/skill_maps.py           # rewrite the generated sections
    python setup/skill_maps.py --check   # exit 1 if any is out of date

The engine map's two module sections (each backend/app module, and for routed
modules the router prefix and route count) and the interface map's module list
and engine command list (the case labels the project engine dispatches on) are
read from the tree. Everything else in the maps is written by hand and left
alone. The maps were once written by hand at 0.56.0 and drifted: 40 engine
modules went unlisted and a retired one stayed.

Only the structure is recorded: a module, a route or a command added, removed or
renamed. Line counts were recorded until 2.11.2, and any edit to a listed module
left the check failing on main until the maps were regenerated.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPS = ROOT / ".claude" / "skills" / "formcut-skillset" / "sub-skills"
ENGINE_MAP = MAPS / "engine-architect" / "references" / "engine-map.md"
INTERFACE_MAP = MAPS / "interface-architect" / "references" / "interface-map.md"
ROUTE = re.compile(r"^@(?:router|app)\.(?:get|post|put|patch|delete|api_route|websocket)\(\s*\"([^\"]*)\"", re.MULTILINE)
PREFIX = re.compile(r"APIRouter\(\s*prefix\s*=\s*\"([^\"]+)\"")
UNROUTED_INTRO = (
    "These are the working parts the routed modules call: the renderer and its\n"
    "helpers, the export graph, decoding, effects, expressions, paths, processes and\n"
    "the automation transports."
)
COMMANDS_INTRO = (
    "Every way a project can change. Anything outside this list is not a command,\nand a UI module that mutates state directly is a defect."
)


def engine_sections() -> dict[str, str]:
    routed, unrouted = [], []
    for path in sorted((ROOT / "backend" / "app").glob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        routes = ROUTE.findall(text)
        if routes:
            prefix = PREFIX.search(text)
            shown = prefix.group(1) if prefix else routes[0]
            routed.append(f"| {path.name} | {shown} | {len(routes)} |")
        else:
            unrouted.append(f"- `{path.name}`")
    table = "| Module | Prefix | Routes |\n| --- | --- | --- |\n" + "\n".join(routed)
    return {
        "Modules that serve routes": table,
        "Modules with no routes of their own": UNROUTED_INTRO + "\n\n" + "\n".join(unrouted),
    }


def interface_sections() -> dict[str, str]:
    src = ROOT / "frontend" / "src"
    modules = sorted(p for p in src.rglob("*.ts") if "node_modules" not in p.parts)
    listing = "\n".join(f"- `{p.relative_to(src).as_posix()}`" for p in modules)
    project = (src / "engine" / "project.ts").read_text(encoding="utf-8")
    commands = sorted(set(re.findall(r'case "([a-z]+\.[A-Za-z.-]+)":', project)))
    return {"Modules": listing, "Engine commands": COMMANDS_INTRO + "\n\n" + "\n".join(f"- `{c}`" for c in commands)}


def splice(text: str, sections: dict[str, str]) -> str:
    for heading, body in sections.items():
        start = text.index(f"\n## {heading}\n") + len(f"\n## {heading}\n")
        end = text.find("\n## ", start)
        end = len(text) if end == -1 else end
        text = text[:start] + "\n" + body + "\n" + text[end:]
    return text


def main() -> int:
    stale = []
    for path, sections in ((ENGINE_MAP, engine_sections()), (INTERFACE_MAP, interface_sections())):
        current = path.read_text(encoding="utf-8")
        updated = splice(current, sections)
        if updated != current:
            stale.append(path)
            if "--check" not in sys.argv[1:]:
                path.write_text(updated, encoding="utf-8")
    if "--check" in sys.argv[1:]:
        for path in stale:
            print(f"{path.relative_to(ROOT)} is out of date: run python setup/skill_maps.py")
        return 1 if stale else 0
    print("rewrote " + (", ".join(p.name for p in stale) or "nothing, both maps were current"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
