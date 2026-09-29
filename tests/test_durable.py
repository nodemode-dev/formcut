"""Durable state files (v2.2.3, after the owner lost media.json): every store in the data folder is written whole and
moved into place with the previous version kept, and a damaged file is set aside and its backup read, never read as
empty and saved over; projects are also kept one file each, to rebuild projects.json from."""

from __future__ import annotations

import json
import os
import stat
import sys

import pytest
from app import durable, providers, store


def test_writes_are_whole_and_keep_the_version_before(tmp_path):
    path = tmp_path / "state.json"
    durable.write_json(path, {"a": 1})
    durable.write_json(path, {"a": 2}, private=True)
    assert json.loads(path.read_text()) == {"a": 2} and json.loads((tmp_path / "state.json.bak").read_text()) == {"a": 1}
    assert not list(tmp_path.glob(".state.json.*.tmp"))
    if sys.platform != "win32":
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600 and stat.S_IMODE(os.stat(tmp_path / "state.json.bak").st_mode) == 0o600


def test_a_damaged_file_is_set_aside_and_its_backup_read(tmp_path):
    path = tmp_path / "state.json"
    durable.write_json(path, ["first"])
    durable.write_json(path, ["second"])
    path.write_text('["half wri')
    assert durable.read_json(path, []) == ["first"]  # the backup, not an empty list
    assert len(list(tmp_path.glob("state.json.damaged-*"))) == 1  # kept for a person to look at
    assert json.loads(path.read_text()) == ["first"]  # and the file put back
    path.unlink()
    (tmp_path / "state.json.bak").unlink()
    assert durable.read_json(path, {"fresh": True}) == {"fresh": True}


def test_the_api_keys_survive_a_damaged_file(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "STORE", tmp_path / "providers.json")
    providers._write({"elevenlabs": "key-one"})
    providers._write({"elevenlabs": "key-one", "civitai": "key-two"})
    (tmp_path / "providers.json").write_text("{")
    assert providers._read() == {"elevenlabs": "key-one"}


@pytest.fixture
def projects(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "PROJECTS_FILE", tmp_path / "projects.json")
    monkeypatch.setattr(store, "RECORDS_DIR", tmp_path / "project-records")
    monkeypatch.setattr(store, "_record_texts", {})
    return tmp_path


def test_projects_come_back_from_a_damaged_file_or_from_their_own_records(projects):
    store.save_project({"id": "one", "title": "One"})
    store.save_project({"id": "two", "title": "Two"})
    store.save_project({"id": "three", "title": "Three"})
    store.delete_project("three")
    (projects / "projects.json").write_text("[{")
    assert sorted(p["id"] for p in store.list_projects()) == ["one", "two"]
    (projects / "projects.json").unlink()
    (projects / "projects.json.bak").unlink()
    rebuilt = store.list_projects()
    assert sorted(p["id"] for p in rebuilt) == ["one", "two"]  # the deleted one stays deleted
    assert next(p for p in rebuilt if p["id"] == "two")["title"] == "Two"
