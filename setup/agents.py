#!/usr/bin/env python3
"""./formcut agents: Claude Code, Codex, Cursor and Antigravity driving formcut.

  sync [--check]    regenerate the formcut-mcp skill's tool reference from the MCP server, write
                    agents/manifest.json (what formcut offers agents) and mirror .claude/skills/formcut-mcp
                    to .agents/skills; --check exits 1 when anything drifted
  install [--dry-run] [claude|codex|cursor|antigravity ...]
                    set the clients up for this user account: the MCP server (./formcut mcp from this checkout)
                    and the formcut-mcp skill; all four by default (Antigravity: the MCP server only, in
                    ~/.gemini/config/mcp_config.json)
  status            which clients are on this computer and whether the skill is in step

Standard library only, so it runs before anything is installed.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "formcut-mcp"
MIRROR = ROOT / ".agents" / "skills" / "formcut-mcp"
LAUNCHER = ROOT / "formcut"
HOME = Path.home()
CLIENTS = ("claude", "codex", "cursor", "antigravity")
MANIFEST = ROOT / "agents" / "manifest.json"
APP = "formcut"
SERVER = ROOT / "backend" / "app" / "agent_mcp.py"
HOST = ROOT / "backend" / "app" / "formext_host.py"
DOCK = {"present": True, "positions": ["bottom", "right"], "tabs": ["shell", "claude", "codex", "cursor"]}
DOCK_DIR = ROOT / "frontend" / "src" / "dock"
DOCK_VERSION = "2.1.0"


def dock_problems(folder: Path = DOCK_DIR) -> list[str]:
    """What is wrong with the shared dock folder: a file that differs from MANIFEST.json, is missing or extra, or imports from the app."""
    import hashlib

    listing = folder / "MANIFEST.json"
    if not listing.is_file():
        return ["frontend/src/dock/MANIFEST.json is missing"]
    manifest = json.loads(listing.read_text(encoding="utf-8"))
    problems = [] if manifest.get("version") == DOCK_VERSION else [f"MANIFEST.json names module {manifest.get('version')}, expected {DOCK_VERSION}"]
    wanted = manifest.get("files", {})
    found = {path.name: path for path in folder.iterdir() if path.is_file() and path.name != "MANIFEST.json"}
    for name in sorted(set(wanted) | set(found)):
        if name not in found:
            problems.append(f"frontend/src/dock/{name} is missing")
        elif name not in wanted:
            problems.append(f"frontend/src/dock/{name} is not in MANIFEST.json")
        elif hashlib.sha256(found[name].read_bytes()).hexdigest() != wanted[name]:
            problems.append(f"frontend/src/dock/{name} differs from MANIFEST.json")
    for name, path in sorted(found.items()):
        if path.suffix != ".ts":
            continue
        for target in re.findall(r"""(?:from|import)\s*\(?\s*['"]([^'"]+)['"]""", path.read_text(encoding="utf-8")):
            if not (target.startswith("./") and "/" not in target[2:]) and not target.startswith("@xterm/"):
                problems.append(f"frontend/src/dock/{name} imports {target} from outside the dock folder")
    return problems


LOOKUP = ROOT / "backend" / "app" / "agent_lookup.py"
LOOKUP_HASHES = {
    "1.0.0": "252ea9bb9419d4990f174f91914f09800497bc69e98f849f5643bbf4217cc3f3",
    "1.0.1": "62667f9b68b7d101e1896ce617240424e33b7e498c560bc79d45f0ab26c77d51",
}


def lookup_problems(path: Path = LOOKUP) -> list[str]:
    """What is wrong with the family's finder for the agent programs: missing, or not the bytes recorded for its version."""
    import hashlib

    rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    try:
        raw = path.read_bytes()
    except OSError:
        return [f"{rel}: missing (the shared finder for the agent programs)"]
    told = re.search(rb'^VERSION = "([^"\r\n]+)"\r?$', raw, re.MULTILINE)
    version = told.group(1).decode("ascii", "replace") if told else "unknown"
    if LOOKUP_HASHES.get(version) != hashlib.sha256(raw).hexdigest():
        return [f"{rel}: does not match the hash recorded for version {version} (the shared finder changes only as a whole new version)"]
    return []


def lookup():
    """The shared finder, loaded from its file: it imports nothing from the app, so this script needs no engine."""
    spec = importlib.util.spec_from_file_location("formcut_agent_lookup", LOOKUP)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _files(folder: Path) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def _declared_tools() -> list[dict]:
    spec = importlib.util.spec_from_file_location("mcp_tool_reference", ROOT / "setup" / "mcp_tool_reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.tools()


def _skill_entries() -> list[dict]:
    base = ROOT / ".claude" / "skills"
    found = []
    for folder in sorted(p for p in base.iterdir() if (p / "SKILL.md").is_file()) if base.is_dir() else []:
        subs = folder / "sub-skills"
        names = sorted(p.name for p in subs.iterdir() if (p / "SUB-SKILL.md").is_file()) if subs.is_dir() else []
        found.append({"name": folder.name, "sub_skills": names})
    return found


def _serves_http() -> bool:
    route = re.compile(r"""\.(?:get|post|put|api_route|route|add_api_route)\(\s*["']/mcp["']|add_route\(\s*["']/mcp["']""")
    return any(route.search(p.read_text(encoding="utf-8")) for p in (ROOT / "backend" / "app").rglob("*.py"))


def manifest_text() -> str:
    listed = _declared_tools()
    tools = [t["name"] for t in listed]
    # The server's gate (agent_mcp._gated_tool) asks the window before every tool that is not read-only.
    gate = re.search(r"^mcp\.tool\s*=\s*_gated_tool\s*$", SERVER.read_text(encoding="utf-8"), re.MULTILINE)
    gated = [t["name"] for t in listed if t["effect"] != "read only"] if gate else []
    transports = (["stdio"] if re.search(r"""\.run\(\s*transport\s*=\s*["']stdio["']""", SERVER.read_text(encoding="utf-8")) else []) + (
        ["http"] if _serves_http() else []
    )
    api = re.search(r"""^API\s*=\s*["']([^"']+)["']""", HOST.read_text(encoding="utf-8"), re.MULTILINE) if HOST.is_file() else None
    body = {
        "format": "form-agent-manifest",
        "version": 1,
        "app": APP,
        "mcp": {
            "tools": tools,
            "read_only": [t["name"] for t in listed if t["effect"] == "read only"],
            "approval_gated": gated,
            "transports": transports,
        },
        "skills": _skill_entries(),
        "dock": DOCK,
        "extensions": {"host_api": api.group(1)} if api else None,
    }
    return json.dumps(body, indent=2) + "\n"


def sync(check: bool) -> int:
    drift = []
    reference = [sys.executable, str(ROOT / "setup" / "mcp_tool_reference.py")] + (["--check"] if check else [])
    run = subprocess.run(reference, capture_output=True, text=True, check=False)
    if run.returncode:
        drift.append(".claude/skills/formcut-mcp/sub-skills/mcp-workflows/references/tools.md")
    wanted = manifest_text()
    if not MANIFEST.is_file() or MANIFEST.read_text(encoding="utf-8") != wanted:
        drift.append(str(MANIFEST.relative_to(ROOT)))
        if not check:
            MANIFEST.parent.mkdir(parents=True, exist_ok=True)
            MANIFEST.write_text(wanted, encoding="utf-8")
    if not MIRROR.exists() or _files(MIRROR) != _files(SKILL):
        drift.append(str(MIRROR.relative_to(ROOT)))
        if not check:
            shutil.rmtree(MIRROR, ignore_errors=True)
            shutil.copytree(SKILL, MIRROR)
    problems = dock_problems()
    for problem in problems:
        print(f"agents: dock module: {problem} (copy the folder again from FormVis; sync never writes it)")
    finder = lookup_problems()
    for problem in finder:
        print(f"agents: {problem}")
    problems = problems + finder
    if check:
        print("agents: in step" if not drift else "agents: drifted: " + ", ".join(drift) + " (run ./formcut agents sync)")
        return 1 if drift or problems else 0
    print("agents: " + ("updated " + ", ".join(drift) if drift else "already in step"))
    return 1 if problems else 0


def _copy_skill(target: Path, dry: bool) -> str:
    if not dry:
        shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SKILL, target)
    return f"skill formcut-mcp -> {target}"


def _claude(dry: bool) -> list[str]:
    lines = []
    command = ["claude", "mcp", "add", "formcut", "--scope", "user", "--", str(LAUNCHER), "mcp"]
    finder = lookup()
    found = finder.check(finder.find("claude", override_vars=("FORMCUT_CLAUDE_BIN",)))
    if found.state == "runs":
        if not dry:
            env = finder.child_env(found.path)
            finder.run([found.path, "mcp", "remove", "formcut", "--scope", "user"], env, 60)
            run = finder.run([found.path, *command[1:]], env, 60)
            if run.returncode:
                lines.append(f"claude: {(run.stderr or run.stdout).strip()[:200]}")
        lines.append("claude: MCP server formcut -> " + " ".join(command[7:]))
    else:
        lines.append("claude: " + finder.sentence(found, finder.install("claude")) + " When it is there: " + " ".join(command))
    lines.append("claude: " + _copy_skill(HOME / ".claude" / "skills" / "formcut-mcp", dry))
    return lines


def _codex(dry: bool) -> list[str]:
    config = HOME / ".codex" / "config.toml"
    block = (
        "\n[mcp_servers.formcut]\n"
        f"command = {json.dumps(str(LAUNCHER))}\n"
        'args = ["mcp"]\n'
        "startup_timeout_sec = 120\n"
        "tool_timeout_sec = 900\n"
    )
    text = config.read_text(encoding="utf-8") if config.exists() else ""
    if "[mcp_servers.formcut]" in text:
        line = f"codex: {config} already has [mcp_servers.formcut]; left as it is"
    else:
        if not dry:
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(text + block, encoding="utf-8")
        line = f"codex: MCP server formcut added to {config}"
    return [line, "codex: " + _copy_skill(HOME / ".agents" / "skills" / "formcut-mcp", dry)]


def _cursor(dry: bool) -> list[str]:
    config = HOME / ".cursor" / "mcp.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
    except ValueError:
        return [f"cursor: {config} is not valid JSON; add mcpServers.formcut by hand: {LAUNCHER} mcp"]
    data.setdefault("mcpServers", {})["formcut"] = {"command": str(LAUNCHER), "args": ["mcp"]}
    if not dry:
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return [f"cursor: MCP server formcut -> {config}"]


def _antigravity(dry: bool) -> list[str]:
    config = HOME / ".gemini" / "config" / "mcp_config.json"
    older = HOME / ".gemini" / "antigravity-cli" / "mcp_config.json"
    lines = []
    if older.exists() and not config.exists():
        lines.append(f"antigravity: an older file was seen at {older} and left alone; the documented file is {config}")
    try:
        data = json.loads(config.read_text(encoding="utf-8") or "{}") if config.exists() else {}
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
        return [*lines, f"antigravity: {config} is not an MCP servers file formcut can read; left alone"]
    entry = {"command": str(LAUNCHER), "args": ["mcp"]}
    have = data.get("mcpServers", {}).get("formcut")
    ours = isinstance(have, dict) and have.get("args") == ["mcp"] and Path(str(have.get("command", ""))).name == LAUNCHER.name
    if have == entry:
        return [*lines, f"antigravity: MCP server formcut already in {config}"]
    if have is not None and not ours:
        return [*lines, f"antigravity: {config} has a server named formcut that formcut did not write; left alone"]
    if not dry:
        data.setdefault("mcpServers", {})["formcut"] = entry
        config.parent.mkdir(parents=True, exist_ok=True)
        part = config.with_name(config.name + ".part")
        part.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        part.replace(config)
    return [*lines, f"antigravity: MCP server formcut -> {config}"]


def install(args: list[str]) -> int:
    dry = "--dry-run" in args
    which = [a for a in args if not a.startswith("--")] or list(CLIENTS)
    unknown = [w for w in which if w not in CLIENTS]
    if unknown:
        print(f"agents: unknown client {', '.join(unknown)} (claude, codex, cursor or antigravity)")
        return 2
    steps = {"claude": _claude, "codex": _codex, "cursor": _cursor, "antigravity": _antigravity}
    for name in which:
        for line in steps[name](dry):
            print(("(dry run) " if dry else "") + line)
    return 0


def clients() -> dict[str, bool]:
    finder = lookup()
    on = {name: finder.find(name, override_vars=(f"FORMCUT_{name.upper()}_BIN",)).path is not None for name in CLIENTS}
    return {
        "claude": on["claude"],
        "codex": on["codex"] or (HOME / ".codex").exists(),
        "cursor": on["cursor"] or (HOME / ".cursor").exists(),
        "antigravity": on["antigravity"] or (HOME / ".gemini").exists(),
    }


def status() -> int:
    for name, on in clients().items():
        print(f"{name}: {'found' if on else 'not found'}")
    return sync(check=True)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv[0] == "sync":
        return sync("--check" in argv[1:])
    if argv[0] == "install":
        return install(argv[1:])
    if argv[0] == "status":
        return status()
    print(f"agents: unknown action {argv[0]}\n{__doc__}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
