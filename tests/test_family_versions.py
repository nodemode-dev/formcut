"""F4, the family version sites (FAMILY_TEST_PLAN layer F4): every place the release commit sets the
version holds the same x.y.z, and the patch number has one digit."""

import json
import re

import pytest
from conftest import ROOT

SITES = [
    ("README.md", r'alt="version v(\d+\.\d+\.\d+)"'),
    ("README.md", r"badge/version-v(\d+\.\d+\.\d+)-"),
    ("backend/app/main.py", r'^APP_VERSION = "([^"]+)"'),
    ("frontend/package.json", r'^  "version": "([^"]+)"'),
    ("frontend/package-lock.json", r'\A\{\s*"name": "[^"]+",\s*"version": "([^"]+)"'),
    ("src-tauri/Cargo.toml", r'^version = "([^"]+)"'),
    ("src-tauri/tauri.conf.json", r'^  "version": "([^"]+)"'),
    ("src-tauri/Cargo.lock", r'name = "formcut"\nversion = "([^"]+)"'),
    ("form-functions.json", r'^  "app_version": "([^"]+)"'),
]


def found():
    values = {}
    for rel, pattern in SITES:
        match = re.search(pattern, (ROOT / rel).read_text(encoding="utf-8"), re.MULTILINE)
        values[f"{rel} {pattern[:24]}"] = match.group(1) if match else None
    return values


def test_every_version_site_was_found():
    missing = [site for site, value in found().items() if value is None]
    assert not missing, missing


def test_every_version_site_agrees():
    assert len(set(found().values())) == 1, found()


def test_the_lockfile_root_package_agrees_with_the_manifest():
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert lock["packages"][""]["version"] == manifest["version"]


def test_version_has_three_parts_and_a_one_digit_patch():
    version = next(iter(found().values()))
    assert re.fullmatch(r"\d+\.\d+\.\d", version), version


@pytest.mark.parametrize("rel", ["src-tauri/tauri.conf.json", "frontend/package.json"])
def test_version_files_parse(rel):
    json.loads((ROOT / rel).read_text(encoding="utf-8"))
