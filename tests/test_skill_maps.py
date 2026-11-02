"""The skillset's reference maps list the modules and commands the tree has.

They were written by hand at 0.56.0 and drifted: 40 engine modules unlisted and a
retired one still named. Their inventory sections are generated now. Until 2.11.2
they also recorded each module's line count, so any edit to a listed module left
this check failing on main until someone regenerated them; they record structure
only now.
"""

import importlib.util
import subprocess
import sys

from conftest import ROOT

ROUTED = 'from fastapi import APIRouter\nrouter = APIRouter(prefix="/api/thing")\n\n\n@router.get("/one")\ndef one():\n    return 1\n'


def _skill_maps():
    spec = importlib.util.spec_from_file_location("skill_maps", ROOT / "setup" / "skill_maps.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree(tmp_path):
    app = tmp_path / "backend" / "app"
    app.mkdir(parents=True)
    (app / "thing.py").write_text(ROUTED, encoding="utf-8")
    (app / "helper.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
    return app


def test_the_generated_map_sections_are_current():
    result = subprocess.run([sys.executable, str(ROOT / "setup" / "skill_maps.py"), "--check"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout


def test_an_edit_inside_a_listed_module_leaves_the_map_current(tmp_path, monkeypatch):
    maps = _skill_maps()
    app = _tree(tmp_path)
    monkeypatch.setattr(maps, "ROOT", tmp_path)
    before = maps.engine_sections()
    (app / "thing.py").write_text(ROUTED + "\n\ndef more():\n    return 3\n", encoding="utf-8")
    (app / "helper.py").write_text("def helper():\n    value = 2\n    return value\n", encoding="utf-8")
    assert maps.engine_sections() == before


def test_a_module_or_route_added_or_removed_makes_the_map_stale(tmp_path, monkeypatch):
    maps = _skill_maps()
    app = _tree(tmp_path)
    monkeypatch.setattr(maps, "ROOT", tmp_path)
    before = maps.engine_sections()
    (app / "helper.py").unlink()
    assert maps.engine_sections() != before
    (app / "helper.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
    assert maps.engine_sections() == before
    (app / "thing.py").write_text(ROUTED + '\n\n@router.post("/two")\ndef two():\n    return 2\n', encoding="utf-8")
    assert "| thing.py | /api/thing | 2 |" in maps.engine_sections()["Modules that serve routes"]
