"""The demo media stays out of every build.

.docs/wiki/Licences.md: the files in examples/demo carry no licence grant, their
rights must be confirmed before public distribution, and examples/demo is not
bundled into frozen builds. freeze.py bundled effect-example-image.jpg from the
first commit until the first release run, where a clean checkout, which never has
the ignored file, stopped the build. The effect thumbnails fall back to a generated
image without it.
"""

from conftest import ROOT


def test_the_freeze_bundles_nothing_from_examples_demo():
    assert "examples" not in (ROOT / "backend" / "freeze.py").read_text(encoding="utf-8")


def test_the_licence_page_still_says_so():
    assert "examples/demo is not bundled into frozen builds" in (ROOT / ".docs" / "wiki" / "Licences.md").read_text(encoding="utf-8")
