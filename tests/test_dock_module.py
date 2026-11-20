"""The shared dock folder is the family's module, unchanged: agents sync fails, naming the file, when it is not."""

import importlib.util
import json
import re
import shutil

from conftest import ROOT

DOCK = ROOT / "frontend" / "src" / "dock"
SOURCE = ROOT / "frontend" / "src"


def _agents():
    spec = importlib.util.spec_from_file_location("formcut_agents_dock", ROOT / "setup" / "agents.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_folder_matches_its_manifest_and_imports_nothing_of_formcut():
    agents = _agents()
    assert agents.dock_problems() == []
    assert json.loads((DOCK / "MANIFEST.json").read_text(encoding="utf-8"))["version"] == agents.DOCK_VERSION == "2.2.0"
    assert len(list(DOCK.iterdir())) == 16


def test_a_changed_an_extra_and_a_missing_file_are_each_named(tmp_path):
    agents = _agents()
    copy = tmp_path / "dock"
    shutil.copytree(DOCK, copy)
    (copy / "keys.ts").write_text((copy / "keys.ts").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    (copy / "extra.ts").write_text("import { t } from '../i18n';\n", encoding="utf-8")
    (copy / "tour.ts").unlink()
    problems = agents.dock_problems(copy)
    assert "frontend/src/dock/keys.ts differs from MANIFEST.json" in problems
    assert "frontend/src/dock/extra.ts is not in MANIFEST.json" in problems
    assert "frontend/src/dock/extra.ts imports ../i18n from outside the dock folder" in problems
    assert "frontend/src/dock/tour.ts is missing" in problems


def test_sync_reports_a_dock_problem_and_fails(monkeypatch, tmp_path, capsys):
    agents = _agents()
    copy = tmp_path / "dock"
    shutil.copytree(DOCK, copy)
    (copy / "dock.css").write_text("", encoding="utf-8")
    real = agents.dock_problems
    monkeypatch.setattr(agents, "dock_problems", lambda: real(copy))
    assert agents.sync(check=True) == 1
    assert "frontend/src/dock/dock.css differs from MANIFEST.json" in capsys.readouterr().out


def test_the_manifest_says_the_dock_is_there_with_the_tabs_the_adapter_offers():
    dock = json.loads((ROOT / "agents" / "manifest.json").read_text(encoding="utf-8"))["dock"]
    assert dock == {"present": True, "positions": ["bottom", "right"], "tabs": ["shell", "claude", "codex", "cursor", "antigravity"]}
    adapter = (SOURCE / "dock-adapter.ts").read_text(encoding="utf-8")
    offered = re.search(r"tabs: \(\) => \(\{ builtin: \[([^\]]+)\]", adapter).group(1)
    assert [word.strip().strip('"') for word in offered.split(",")] == dock["tabs"]


def test_the_storage_key_is_the_docks_alone_and_the_boot_script_reserves_from_it():
    adapter = (SOURCE / "dock-adapter.ts").read_text(encoding="utf-8")
    assert 'DOCK_KEY = "formcut.dock"' in adapter and "legacy: []" in adapter
    others = [path for path in SOURCE.rglob("*.ts") if DOCK not in path.parents and path.name != "dock-adapter.ts" and '"formcut.dock"' in path.read_text(encoding="utf-8")]
    assert others == []
    boot = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'localStorage.getItem("formcut.dock")' in boot
    for name in ("data-ft-dock", "data-ft-dock-side", "data-ft-dock-h", "data-ft-dock-w", "--ft-dock-size", "--ft-dock-wsize"):
        assert f'"{name}"' in boot, name
    sizes = re.search(r"DOCK_SIZES = \{([^}]+)\}", adapter).group(1)
    for part in ("minHeight: 120", "maxHeightShare: 0.45", "keepHeight: 440", "minWidth: 320", "maxWidthShare: 0.4", "keepWidth: 940"):
        assert part in sizes, part
    for number in ("0.4, window.innerWidth - 940", "0.45, window.innerHeight - 440", "Math.max(320", "Math.max(120"):
        assert number in boot, number


def test_the_old_dialog_and_the_old_socket_are_gone_from_the_window():
    assert not (SOURCE / "ui" / "agent-access.ts").exists()
    for path in SOURCE.rglob("*.ts"):
        text = path.read_text(encoding="utf-8")
        assert "/api/terminal/ws" not in text, path.name
        assert "askAgentAccess" not in text, path.name


def test_the_finder_for_the_agent_programs_is_the_family_s_file_at_a_recorded_version(tmp_path):
    agents = _agents()
    assert agents.lookup_problems() == []
    version = re.search(r'^VERSION = "([^"]+)"$', agents.LOOKUP.read_text(encoding="utf-8"), re.MULTILINE).group(1)
    assert version in agents.LOOKUP_HASHES
    changed = tmp_path / "agent_lookup.py"
    changed.write_bytes(agents.LOOKUP.read_bytes() + b"\n")
    assert agents.lookup_problems(changed) == [
        f"{changed}: does not match the hash recorded for version {version} (the shared finder changes only as a whole new version)"
    ]
    assert agents.lookup_problems(tmp_path / "gone.py") == [f"{tmp_path / 'gone.py'}: missing (the shared finder for the agent programs)"]
