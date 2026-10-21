#!/usr/bin/env python3
"""./formcut agents: Claude Code, Codex and Cursor driving formcut.

  sync [--check]    regenerate the formcut-mcp skill's tool reference from the MCP server and mirror
                    .claude/skills/formcut-mcp to .agents/skills; --check exits 1 when anything drifted
  install [--dry-run] [claude|codex|cursor ...]
                    set the clients up for this user account: the MCP server (./formcut mcp from this checkout)
                    and the formcut-mcp skill; all three by default
  status            which clients are on this computer and whether the skill is in step

Standard library only, so it runs before anything is installed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / ".claude" / "skills" / "formcut-mcp"
MIRROR = ROOT / ".agents" / "skills" / "formcut-mcp"
LAUNCHER = ROOT / "formcut"
HOME = Path.home()
CLIENTS = ("claude", "codex", "cursor")


def _files(folder: Path) -> dict:
    return {str(p.relative_to(folder)): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def sync(check: bool) -> int:
    drift = []
    reference = [sys.executable, str(ROOT / "setup" / "mcp_tool_reference.py")] + (["--check"] if check else [])
    run = subprocess.run(reference, capture_output=True, text=True, check=False)
    if run.returncode:
        drift.append(".claude/skills/formcut-mcp/sub-skills/mcp-workflows/references/tools.md")
    if not MIRROR.exists() or _files(MIRROR) != _files(SKILL):
        drift.append(str(MIRROR.relative_to(ROOT)))
        if not check:
            shutil.rmtree(MIRROR, ignore_errors=True)
            shutil.copytree(SKILL, MIRROR)
    if check:
        print("agents: in step" if not drift else "agents: drifted: " + ", ".join(drift) + " (run ./formcut agents sync)")
        return 1 if drift else 0
    print("agents: " + ("updated " + ", ".join(drift) if drift else "already in step"))
    return 0


def _copy_skill(target: Path, dry: bool) -> str:
    if not dry:
        shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SKILL, target)
    return f"skill formcut-mcp -> {target}"


def _claude(dry: bool) -> list[str]:
    lines = []
    command = ["claude", "mcp", "add", "formcut", "--scope", "user", "--", str(LAUNCHER), "mcp"]
    if shutil.which("claude"):
        if not dry:
            subprocess.run(["claude", "mcp", "remove", "formcut", "--scope", "user"], capture_output=True, check=False)
            run = subprocess.run(command, capture_output=True, text=True, check=False)
            if run.returncode:
                lines.append(f"claude: {(run.stderr or run.stdout).strip()[:200]}")
        lines.append("claude: MCP server formcut -> " + " ".join(command[7:]))
    else:
        lines.append("claude: not found on PATH; when it is: " + " ".join(command))
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


def install(args: list[str]) -> int:
    dry = "--dry-run" in args
    which = [a for a in args if not a.startswith("--")] or list(CLIENTS)
    unknown = [w for w in which if w not in CLIENTS]
    if unknown:
        print(f"agents: unknown client {', '.join(unknown)} (claude, codex or cursor)")
        return 2
    steps = {"claude": _claude, "codex": _codex, "cursor": _cursor}
    for name in which:
        for line in steps[name](dry):
            print(("(dry run) " if dry else "") + line)
    return 0


def clients() -> dict[str, bool]:
    return {
        "claude": bool(shutil.which("claude")),
        "codex": bool(shutil.which("codex")) or (HOME / ".codex").exists(),
        "cursor": bool(shutil.which("cursor")) or (HOME / ".cursor").exists(),
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
