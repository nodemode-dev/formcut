"""Models on first use, not on first launch.

First launch used to fetch every permissively licensed model and six Whisper
variants, about 1.4 GB, before a person had used any of them. It now fetches
only the default cutout; everything else arrives when first used.
"""

from __future__ import annotations

import pytest
from app import model_manager


@pytest.fixture
def recorded(monkeypatch) -> dict:
    seen = {"models": [], "hub": []}
    monkeypatch.setattr(model_manager, "ready", lambda model: False)
    monkeypatch.setattr(model_manager, "_tracked", lambda model, report, cancelled: seen["models"].append(model) or {"model": model})
    monkeypatch.setattr(model_manager, "hub_fetch", lambda model, path: seen["hub"].append((model, path)))
    return seen


def run_startup(monkeypatch, mode: str | None) -> None:
    started = []
    monkeypatch.setattr(model_manager.jobs, "submit", lambda kind, operation: started.append(operation) or {"job_id": "j"})
    if mode is None:
        monkeypatch.delenv("FORMCUT_MODELS_AUTO", raising=False)
    else:
        monkeypatch.setenv("FORMCUT_MODELS_AUTO", mode)
    model_manager.auto_download()
    started[0]("j", lambda fraction: None, lambda: False)


def test_first_launch_fetches_only_the_default_cutout(recorded):
    model_manager.prepare(lambda fraction: None, lambda: False, True)
    assert recorded["models"] == list(model_manager.FIRST_LAUNCH) == ["object-cutout"]


def test_first_launch_fetches_no_whisper_files(recorded):
    model_manager.prepare(lambda fraction: None, lambda: False, True)
    assert recorded["hub"] == []


def test_everything_brings_every_whisper_file(recorded):
    model_manager.prepare(lambda fraction: None, lambda: False, True, True)
    assert len(recorded["hub"]) == sum(len(paths) for paths in model_manager.HUB_PREFETCH.values())


def test_a_model_already_there_is_not_fetched_again(recorded, monkeypatch):
    monkeypatch.setattr(model_manager, "ready", lambda model: model == "object-cutout")
    model_manager.prepare(lambda fraction: None, lambda: False, True)
    assert recorded["models"] == []


def test_the_default_start_fetches_the_first_launch_set(recorded, monkeypatch):
    run_startup(monkeypatch, None)
    assert recorded["models"] == ["object-cutout"] and recorded["hub"] == []


def test_all_fetches_every_permissive_model_for_an_offline_machine(recorded, monkeypatch):
    run_startup(monkeypatch, "all")
    # every permissive model but the optional ones: Krea 2's builds and its filter wait for its licence and choices
    permissive = [
        m for m in model_manager.MODELS if "GPL" not in model_manager.MODELS[m]["license"] and not model_manager.MODELS[m].get("optional")
    ]
    assert recorded["models"] == permissive and "video-matting" not in recorded["models"]
    assert not any(m.startswith("krea-2") or m == "nsfw-filter" for m in recorded["models"])


def test_zero_fetches_nothing(recorded, monkeypatch):
    run_startup(monkeypatch, "0")
    assert recorded == {"models": [], "hub": []}


def test_the_first_launch_set_is_registered_and_permissive():
    assert all(
        model in model_manager.MODELS and "GPL" not in model_manager.MODELS[model]["license"] for model in model_manager.FIRST_LAUNCH
    )


def test_whisper_arrives_on_first_use_through_the_hub_route(monkeypatch, tmp_path):
    asked = []
    target = tmp_path / "config.json"
    target.write_text("{}")
    monkeypatch.setattr(model_manager, "hub_fetch", lambda model, path: asked.append((model, path)) or target)
    response = model_manager.hub_file("Xenova", "whisper-tiny.en", "main", "config.json")
    assert asked == [("Xenova/whisper-tiny.en", "config.json")] and response.path == target
