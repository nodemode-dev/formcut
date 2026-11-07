"""The demo media ships inside the app, and NOTICE credits every file.

Since 2.12.6 backend/freeze.py adds the four files in examples/demo to the frozen
engine, where app/demo.py finds them under sys._MEIPASS for the first-run demo.
NOTICE ships with the app (src-tauri resources), so it must name each file with its
creator, source and licence; a new demo file without a credit fails here.
"""

import ast

from conftest import ROOT

DEMO = ROOT / "examples" / "demo"
NOT_MEDIA = {"README.md", ".gitkeep"}


def _tuple_or_list(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return [ast.literal_eval(e) for e in node.value.elts]
    raise AssertionError(f"{name} not found in {path}")


def _media():
    return sorted(p.name for p in DEMO.iterdir() if p.is_file() and p.name not in NOT_MEDIA)


def test_the_freeze_bundles_every_file_the_demo_loads():
    frozen = _tuple_or_list(ROOT / "backend" / "freeze.py", "DEMO_FILES")
    loaded = _tuple_or_list(ROOT / "backend" / "app" / "demo.py", "FILES")
    assert sorted(frozen) == sorted(loaded)
    assert sorted(frozen) == _media()


def test_the_freeze_puts_them_where_the_loader_looks():
    freeze = (ROOT / "backend" / "freeze.py").read_text(encoding="utf-8")
    demo = (ROOT / "backend" / "app" / "demo.py").read_text(encoding="utf-8")
    assert '"examples/demo"' in freeze
    assert 'Path(getattr(sys, "_MEIPASS", "")) / "examples" / "demo"' in demo


def test_notice_credits_every_demo_file():
    notice = (ROOT / "NOTICE").read_text(encoding="utf-8")
    section = notice.split("Demo media\n----------", 1)
    assert len(section) == 2, "NOTICE has no Demo media section"
    entries = section[1].split("\n- ")
    for name in _media():
        entry = " ".join(next((e for e in entries if e.lstrip("- ").startswith(f"{name}:")), "").split())
        assert entry, f"{name} has no credit in NOTICE"
        assert " by " in entry or "generated" in entry, f"{name} credit names no creator"
        assert "https://" in entry, f"{name} credit has no source link"
        assert "License" in entry or "Apache-2.0" in entry, f"{name} credit names no licence"


def test_the_licence_page_says_they_ship():
    licences = (ROOT / ".docs" / "wiki" / "Licences.md").read_text(encoding="utf-8")
    assert "not bundled into frozen builds" not in licences
    assert "ship inside the frozen engine" in licences
