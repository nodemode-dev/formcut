"""Importing an effect package from the interface.

An upload is a manifest.json or a .zip of a package folder. It is checked by the
same loader as every package before it is kept, only a package's three file
names are ever taken from it, and they are written under those names, so a zip
cannot put anything outside the package's own folder.
"""

import io
import json
import zipfile

import pytest
from app import effect_packages
from app.catalogue import catalogue

STACK = {
    "id": "my-warm",
    "name": "My Warm",
    "kind": "video",
    "stack": [{"grade": {"temperature": 0.3}}, {"effect": "grain", "amount": 0.3}],
}


@pytest.fixture(autouse=True)
def clean_packages():
    yield
    if effect_packages.PACKAGES.exists():
        import shutil

        shutil.rmtree(effect_packages.PACKAGES)
    effect_packages.reload()


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_a_manifest_imports_and_shows_under_packages():
    added = effect_packages.install(json.dumps(STACK).encode(), "manifest.json")
    assert added == {"id": "my-warm", "name": "My Warm", "kind": "video", "replaced": False}
    listed = [e for e in catalogue()["video"] if e["id"] == "my-warm"]
    assert listed and listed[0]["group"] == "Packages"


def test_a_zip_made_on_a_mac_imports():
    data = _zip(
        {"my-warm/manifest.json": json.dumps(STACK).encode(), "__MACOSX/my-warm/._manifest.json": b"junk", "my-warm/.DS_Store": b"junk"}
    )
    assert effect_packages.install(data, "my-warm.zip")["id"] == "my-warm"


def test_a_zip_whose_names_climb_out_is_refused_and_writes_nothing():
    data = _zip({"../../evil/manifest.json": json.dumps(STACK).encode()})
    with pytest.raises(ValueError, match="no manifest"):
        effect_packages.install(data, "evil.zip")
    assert not any(effect_packages.DATA_DIR.parent.rglob("evil")), "nothing lands outside the package folder"
    assert not (effect_packages.PACKAGES / "my-warm").exists()


def test_a_zip_that_unpacks_too_large_is_refused_before_it_is_read():
    data = _zip({"manifest.json": json.dumps(STACK).encode(), "shader.wgsl": b"\\0" * 5_000_000})
    assert len(data) < 100_000
    with pytest.raises(ValueError, match="more than 4 MB"):
        effect_packages.install(data, "bomb.zip")


def test_a_package_that_would_not_load_is_refused_and_leaves_nothing():
    bad = {**STACK, "stack": [{"effect": "no-such-effect"}]}
    with pytest.raises(ValueError, match="names no built-in effect"):
        effect_packages.install(json.dumps(bad).encode(), "manifest.json")
    assert not (effect_packages.PACKAGES / "my-warm").exists()
    assert not any((effect_packages.DATA_DIR / "effects-incoming").glob("*"))


def test_a_look_cannot_be_replaced_or_removed():
    effect_packages.reload()
    with pytest.raises(ValueError, match="formcut's own looks"):
        effect_packages.install(json.dumps({**STACK, "id": "golden-hour"}).encode(), "manifest.json")
    with pytest.raises(PermissionError):
        effect_packages.remove("golden-hour")


def test_importing_again_updates_and_removing_deletes():
    effect_packages.install(json.dumps(STACK).encode(), "manifest.json")
    again = effect_packages.install(json.dumps({**STACK, "name": "My Warmer"}).encode(), "manifest.json")
    assert again["replaced"] and effect_packages.find("my-warm")["name"] == "My Warmer"
    effect_packages.remove("my-warm")
    assert effect_packages.find("my-warm") is None and not (effect_packages.PACKAGES / "my-warm").exists()


def test_something_that_is_not_a_package_says_what_a_package_is():
    with pytest.raises(ValueError, match=r"zip of its folder, or its manifest\.json"):
        effect_packages.install(b"GIF89a not a package", "picture.gif")


def test_a_package_a_saved_project_uses_cannot_be_removed(monkeypatch):
    from app import store

    effect_packages.install(json.dumps(STACK).encode(), "manifest.json")
    saved = [
        {
            "id": "p1",
            "name": "Trip edit",
            "timelines": [{"tracks": [{"clips": [{"id": "c", "effects": [{"id": "my-warm", "amount": 1}]}]}]}],
        }
    ]
    monkeypatch.setattr(store, "list_projects", lambda: saved)
    with pytest.raises(effect_packages.PackageInUse, match="Trip edit"):
        effect_packages.remove("my-warm")
    assert effect_packages.find("my-warm") is not None
