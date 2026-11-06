"""The demo media ship inside every build, with their credits.

Until 2.12.4 examples/demo was left out of frozen builds, so the demo project opened with no clips, voice or still
("Demo media is not included in this build", backend/app/demo.py) on every released copy. The demo is the first-run
experience, so the folder is bundled where demo_dir() reads it (_MEIPASS/examples/demo), README of credits included.
"""

from app.demo import FILES
from conftest import ROOT


def test_the_freeze_bundles_examples_demo_where_the_engine_reads_it():
    freeze = (ROOT / "backend" / "freeze.py").read_text(encoding="utf-8")
    assert "str(root.parent / 'examples' / 'demo') + os.pathsep + 'examples/demo'" in freeze
    demo = (ROOT / "backend" / "app" / "demo.py").read_text(encoding="utf-8")
    assert 'Path(getattr(sys, "_MEIPASS", "")) / "examples" / "demo"' in demo


def test_every_demo_file_the_project_loads_is_in_the_bundled_folder_with_its_credit():
    folder = ROOT / "examples" / "demo"
    credits = (folder / "README.md").read_text(encoding="utf-8")
    for name in FILES:
        assert (folder / name).is_file() and f"`{name}`" in credits, name


def test_the_licence_page_says_the_demo_media_ship_with_their_own_licences():
    page = (ROOT / ".docs" / "wiki" / "Licences.md").read_text(encoding="utf-8")
    assert "bundled into frozen builds as the demo project's media" in page
