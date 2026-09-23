"""formcut's library of looks, and the stack packages it is made of.

A video package used to be a filter chain nothing rendered: listing one was
harmless, using one made every render of that project fail. A video package is
now a stack of formcut's own effects and grades, run by the same code as every
other effect, and formcut ships 180 of them.
"""

import hashlib
import importlib.util
import json

import numpy as np
import pytest
from app import effect_packages
from app.catalogue import package_entries
from app.pixel_effects import apply_effects
from conftest import ROOT


@pytest.fixture(scope="module")
def library():
    effect_packages.reload()
    return [entry for entry in effect_packages.entries("video") if entry.get("library")]


def _frame():
    y, x = np.mgrid[:36, :64]
    return np.dstack([x * 4, y * 7, (x + y) * 2, np.full_like(x, 255)]).astype(np.uint8)


def test_the_library_is_current_and_loads_without_a_failure(library):
    spec = importlib.util.spec_from_file_location("effect_library", ROOT / "setup" / "effect_library.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert set(module.manifests()) == {entry["id"] for entry in library}
    assert len(library) == 180 and not [f for f in effect_packages.failures() if f["package"] in module.manifests()]


def test_every_look_renders_and_no_two_are_the_same(library):
    seen = {}
    for entry in library:
        out = apply_effects(_frame(), [{"id": entry["id"], "amount": 1}], 0.5)
        assert out.shape == (36, 64, 4) and out.dtype == np.uint8
        seen.setdefault(hashlib.sha256(out.tobytes()).hexdigest(), entry["id"])
    assert len(seen) == 180


def test_a_look_at_half_strength_sits_between_none_and_full(library):
    look = library[0]["id"]
    none, half, full = (apply_effects(_frame(), [{"id": look, "amount": a}], 0.5).astype(int) for a in (0.0, 0.5, 1.0))
    assert np.array_equal(none, _frame().astype(int)) and not np.array_equal(half, full)


def test_the_catalogue_lists_looks_with_their_names(library):
    entry = next(e for e in package_entries("video") if e["id"] == "golden-hour-grain")
    assert entry["group"] == "Looks" and entry["names"]["de"] == "Goldene Stunde · Körnung"


def _package(tmp_path, manifest, chain=None):
    folder = tmp_path / manifest.get("id", "x")
    folder.mkdir()
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if chain:
        (folder / "chain.txt").write_text(chain, encoding="utf-8")
    return folder


@pytest.mark.parametrize(
    ("stack", "reason"),
    [
        ([{"effect": "no-such-effect"}], "names no built-in effect"),
        ([{"grade": {"warp": 1}}], "which a grade does not have"),
        ([{"grade": {"exposure": 9}}], "outside"),
        ([{"effect": "grain", "amount": 2}], "outside 0 to 1"),
        ([], "one to 8 steps"),
    ],
)
def test_a_stack_that_would_not_render_is_refused_with_its_reason(tmp_path, stack, reason):
    folder = _package(tmp_path, {"id": "mine", "name": "Mine", "kind": "video", "stack": stack})
    with pytest.raises(ValueError, match=reason):
        effect_packages.load_package(folder)


def test_a_video_filter_chain_is_refused_rather_than_breaking_renders(tmp_path):
    folder = _package(tmp_path, {"id": "chain", "name": "Chain", "kind": "video"}, chain="volume=2")
    with pytest.raises(ValueError, match="stack of formcut's effects"):
        effect_packages.load_package(folder)


def test_a_persons_package_cannot_take_a_looks_id(tmp_path, monkeypatch, library):
    _package(tmp_path, {"id": "golden-hour", "name": "Mine", "kind": "video", "stack": [{"effect": "grain"}]})
    monkeypatch.setattr(effect_packages, "PACKAGES", tmp_path)
    effect_packages.reload()
    assert any(f["package"] == "golden-hour" and "already used" in f["reason"] for f in effect_packages.failures())
    assert effect_packages.find("golden-hour")["library"] is True
    monkeypatch.undo()
    effect_packages.reload()


def test_the_frozen_engine_carries_the_library():
    assert "effect_library" in (ROOT / "backend" / "freeze.py").read_text(encoding="utf-8")
