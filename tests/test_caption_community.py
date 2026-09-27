"""Caption looks that move, and the community's looks: the two animated word modes (reveal, rise) draw as they
should at the start and the end of a word's ease; the shipped looks all draw a card; every word style keeps moving
through one renderer; Share this look saves a zip made as the community registry's packages are, which the installer
and setup/registry_entry.py take; every package the registry lists matches its hash and installs."""

from __future__ import annotations

import json

import numpy as np
import pytest
from app import effect_packages, presets
from app.main import app
from app.renderer import WORD_EASE, FrameRenderer
from fastapi.testclient import TestClient

WORDS = ["the", "word", "being", "spoken"]
TIMING = [{"t": i * 0.25, "d": 0.25, "text": word} for i, word in enumerate(WORDS)]


def _frame(mode: str, at: float, colour: str = "#ffd633") -> np.ndarray:
    style = {
        "content": " ".join(WORDS),
        "size": 8,
        "color": "#ffffff",
        "bold": True,
        "align": "center",
        "outlineWidth": 0,
        "wordStyle": {"mode": mode, "colour": colour},
    }
    clip = {"id": "c", "kind": "text", "label": "c", "start": 0, "duration": 1, "textStyle": style, "words": TIMING}
    project = {
        "title": "p",
        "width": 320,
        "height": 180,
        "fps": 30,
        "duration": 1,
        "activeTimeline": 0,
        "timelines": [{"id": "p", "name": "p", "tracks": [{"id": "t", "name": "V", "clips": [clip]}]}],
    }
    return FrameRenderer(project).frame(at).astype(int)


def _ink(frame: np.ndarray) -> int:
    return int((frame[..., :3].max(axis=2) > 128).sum())


def _gold(frame: np.ndarray) -> int:
    r, g, b = frame[..., 0], frame[..., 1], frame[..., 2]
    return int(((r > 200) & (g > 150) & (b < 120)).sum())


def test_reveal_draws_only_the_words_spoken_and_fades_the_newest_in():
    before = _frame("reveal", 0.24)  # "the" and "word" not yet: only "the"
    arrived = _frame("reveal", 0.25)  # "word" starts, fully transparent at the start of its ease
    settled = _frame("reveal", 0.25 + WORD_EASE + 0.02)
    last = _frame("reveal", 0.95)
    # the new word is there but not yet seen (its ease has not begun), and the word before it is no longer lit
    assert _ink(arrived) == _ink(before) and _gold(arrived) == 0 < _gold(before)
    assert _gold(settled) > 0 and _ink(before) < _ink(settled) < _ink(last)


def test_rise_settles_where_highlight_draws_the_word():
    settled = _frame("rise", 0.25 + WORD_EASE + 0.02)
    assert np.array_equal(settled, _frame("highlight", 0.25 + WORD_EASE + 0.02))
    assert not np.array_equal(_frame("rise", 0.28), settled)  # mid-ease: lower and fainter


def test_every_shipped_look_draws_a_card_and_the_animated_ones_are_among_them():
    from app.effect_previews import caption_style_preview

    ids = [look["id"] for look in presets.CAPTION_STYLES]
    assert len(ids) == len(set(ids)) == 14
    assert {"word-by-word", "reveal-gold", "reveal-plate", "rise", "rise-sunset", "rise-neon"} <= set(ids)
    for look in presets.CAPTION_STYLES:
        card = caption_style_preview(look["id"])
        assert card.shape[0] > 0 and card[..., :3].max() > 0, look["id"]


def _look(folder, look_id: str, author: str = "someone", mode: str = "rise") -> None:
    folder.mkdir(parents=True)
    manifest = {
        "id": look_id,
        "name": look_id.title(),
        "kind": "captions",
        "author": author,
        "style": {"size": 6, "wordStyle": {"mode": mode, "colour": "#7cf0ff"}},
    }
    (folder / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_share_saves_a_zip_the_installer_and_the_registry_take(tmp_path):
    import hashlib
    import io
    import sys
    import zipfile
    from pathlib import Path

    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    style = {"size": 6.5, "color": "#fff4e8", "bold": True, "wordStyle": {"mode": "reveal", "colour": "#ff8a3d"}}
    shared = client.post("/api/presets/captions/share", json={"name": "Night bus!", "author": "@Ana_B", "style": style})
    assert shared.status_code == 200 and shared.headers["content-type"] == "application/zip"
    assert 'filename="night-bus-by-ana-b.zip"' in shared.headers["content-disposition"]
    assert shared.headers["x-formcut-sha256"] == hashlib.sha256(shared.content).hexdigest()
    with zipfile.ZipFile(io.BytesIO(shared.content)) as archive:
        assert archive.namelist() == ["manifest.json"]
        manifest = json.loads(archive.read("manifest.json"))
    assert manifest["id"] == "night-bus-by-ana-b" and manifest["author"] == "Ana_B" and manifest["style"] == style
    # the same look makes the same bytes, so its hash in the registry holds
    again = client.post("/api/presets/captions/share", json={"name": "Night bus!", "author": "@Ana_B", "style": style})
    assert again.content == shared.content
    # the registry tool takes it as it is
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "setup"))
    import registry_entry

    entry = registry_entry.entry_for(shared.content, "Warm words, the new one fading in.")
    assert entry["id"] == "night-bus-by-ana-b" and entry["author"] == "Ana_B" and entry["kind"] == "captions"
    assert entry["sha256"] == shared.headers["x-formcut-sha256"] and entry["url"].endswith("/packages/night-bus-by-ana-b.zip")
    # a name formcut's own look has is kept apart; a key the caption track does not take is refused
    renamed = client.post("/api/presets/captions/share", json={"name": "Rise", "style": style})
    assert 'filename="rise-look.zip"' in renamed.headers["content-disposition"]
    refused = client.post("/api/presets/captions/share", json={"name": "x", "style": {"weird": 1}})
    assert refused.status_code == 400 and "does not take" in refused.json()["detail"]


def test_every_registry_package_matches_its_hash_and_installs(tmp_path):
    import hashlib
    from pathlib import Path

    registry = Path(__file__).resolve().parents[1] / ".docs" / "registry"
    index = json.loads((registry / "effects-registry.json").read_text(encoding="utf-8"))
    ids = [entry["id"] for entry in index["packages"]]
    assert len(ids) == len(set(ids))
    for entry in index["packages"]:
        data = (registry / "packages" / entry["url"].rsplit("/", 1)[-1]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["id"]
        folder = tmp_path / entry["id"]
        folder.mkdir()
        # the files as the installer takes them from a zip (a package's folder may be the zip's top level)
        for name, content in effect_packages._files_from(data, f"{entry['id']}.zip").items():
            (folder / name).write_bytes(content)
        loaded = effect_packages.load_package(folder)
        assert loaded["id"] == entry["id"] and loaded["kind"] == entry["kind"], entry["id"]


@pytest.mark.parametrize("mode", ["reveal", "rise"])
def test_packages_take_the_animated_modes(tmp_path, mode):
    _look(tmp_path / "moving", "moving", mode=mode)
    assert effect_packages.load_package(tmp_path / "moving")["style"]["wordStyle"]["mode"] == mode


@pytest.mark.parametrize("mode", ["highlight", "pop", "box", "reveal", "rise"])
def test_a_word_styled_caption_moves_through_one_renderer(mode):
    """Playback and export draw every frame through one renderer: its text cache must not hold a caption whose
    lit word moves (it did, for every word style, from R8's cache until v2.0.3)."""
    style = {"content": " ".join(WORDS), "size": 8, "color": "#ffffff", "bold": True, "align": "center", "outlineWidth": 0}
    clip = {"id": "c", "kind": "text", "label": "c", "start": 0, "duration": 1, "words": TIMING}
    clip["textStyle"] = {**style, "wordStyle": {"mode": mode, "colour": "#ffd633"}}
    project = {
        "title": "p",
        "width": 320,
        "height": 180,
        "fps": 30,
        "duration": 1,
        "activeTimeline": 0,
        "timelines": [{"id": "p", "name": "p", "tracks": [{"id": "t", "name": "V", "clips": [clip]}]}],
    }
    renderer = FrameRenderer(project)
    early, late = renderer.frame(0.1), renderer.frame(0.9)
    assert not np.array_equal(early, late)
    assert np.array_equal(late, FrameRenderer(project).frame(0.9))
