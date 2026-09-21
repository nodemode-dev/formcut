"""The compact layout switches on one condition, written the same in the scripts and every stylesheet."""

import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..", "frontend", "src")


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as handle:
        return handle.read()


def test_the_stylesheets_switch_on_the_scripts_condition_and_the_desktop_on_its_complement():
    condition = re.search(r'COMPACT = "([^"]+)"', _read("ui", "compact.ts")).group(1)
    assert condition == "(max-width: 940px), (max-height: 500px)"
    uses = {name: _read("styles", name).count(f"@media {condition}") for name in ("app.css", "containers.css", "settings.css")}
    assert uses == {"app.css": 1, "containers.css": 2, "settings.css": 1}, uses
    assert "@media (min-width: 941px) and (min-height: 501px)" in _read("styles", "creator.css")


def test_the_old_breakpoint_is_gone_from_styles_and_scripts():
    for name in os.listdir(os.path.join(ROOT, "styles")):
        text = _read("styles", name)
        assert "max-width: 768px" not in text and "min-width: 769px" not in text, name
    for folder, _, files in os.walk(os.path.join(ROOT, "ui")):
        for name in files:
            if name.endswith(".ts"):
                with open(os.path.join(folder, name), encoding="utf-8") as handle:
                    assert "innerWidth > 768" not in handle.read(), name


def test_touch_sizes_apply_to_coarse_pointers_only():
    css = _read("styles", "app.css")
    block = css.split("@media (pointer: coarse) {")[1].split("\n}\n")[0]
    assert "min-height: 32px" in block and "min-height: 36px" in block
    assert css.count("@media (pointer: coarse)") == 1
