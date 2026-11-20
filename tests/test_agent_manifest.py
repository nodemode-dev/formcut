"""agents/manifest.json says what formcut offers agents, and it is the file `agents sync` would write."""

import importlib.util
import json
import subprocess
import sys

from conftest import ROOT


def _agents():
    spec = importlib.util.spec_from_file_location("formcut_agents", ROOT / "setup" / "agents.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_manifest_is_what_sync_writes():
    agents = _agents()
    assert agents.MANIFEST.read_text(encoding="utf-8") == agents.manifest_text(), "run ./formcut agents sync"


def test_sync_check_passes_on_the_committed_tree():
    done = subprocess.run(
        [sys.executable, str(ROOT / "setup" / "agents.py"), "sync", "--check"], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_manifest_lists_the_servers_tools_and_keeps_its_subsets_inside_them():
    data = json.loads((ROOT / "agents" / "manifest.json").read_text(encoding="utf-8"))
    assert data["format"] == "form-agent-manifest" and data["version"] == 1 and data["app"] == "formcut"
    mcp = data["mcp"]
    assert mcp["tools"] and len(mcp["tools"]) == len(set(mcp["tools"]))
    assert set(mcp["read_only"]) <= set(mcp["tools"]) and set(mcp["approval_gated"]) <= set(mcp["tools"])
    assert mcp["transports"] == ["stdio"]
    assert [s["name"] for s in data["skills"]] == sorted(
        p.name for p in (ROOT / ".claude" / "skills").iterdir() if (p / "SKILL.md").is_file()
    )
