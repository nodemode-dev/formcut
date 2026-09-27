"""Caption looks that move, and the community's looks: the two animated word modes (reveal, rise) draw as they
should at the start and the end of a word's ease; the shipped looks all draw a card; the community registry takes a
folder only when it loads as a package, names its author and keeps its own id; Share this look writes a file the
package installer takes and the registry takes."""

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


def test_the_registry_lists_community_looks_after_formcuts_with_their_authors(tmp_path, monkeypatch):
    monkeypatch.setattr(presets, "COMMUNITY", tmp_path)
    _look(tmp_path / "night-bus-by-ana", "night-bus-by-ana", "ana")
    _look(tmp_path / "rise", "rise")  # an id formcut's own look has: left out
    (tmp_path / "broken").mkdir()
    (tmp_path / "broken" / "manifest.json").write_text('{"id": "broken", "name": "B", "kind": "captions", "style": {"weird": 1}}')
    listed = presets.list_caption_styles()
    community = [look for look in listed if look.get("community")]
    assert [(look["id"], look["author"]) for look in community] == [("night-bus-by-ana", "ana")]
    assert listed.index(community[0]) == len(presets.CAPTION_STYLES)
    assert presets.caption_style("night-bus-by-ana")["style"]["wordStyle"]["mode"] == "rise"


def test_the_shipped_registry_is_sound():
    """Every folder in backend/app/community_looks loads, has an author, and keeps an id of its own."""
    folders = [p for p in presets.COMMUNITY.iterdir() if p.is_dir()] if presets.COMMUNITY.is_dir() else []
    seen = set(presets.CAPTION_STYLE_IDS)
    for folder in folders:
        entry = effect_packages.load_package(folder)
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        assert entry["kind"] == "captions" and manifest.get("author"), folder.name
        assert entry["id"] == folder.name and entry["id"] not in seen, folder.name
        seen.add(entry["id"])
    assert (presets.COMMUNITY / "README.md").exists()


def test_share_writes_a_package_the_installer_and_the_registry_take(tmp_path, monkeypatch):
    client = TestClient(app, base_url="http://127.0.0.1:8123", headers={"x-formcut-local": "1"})
    style = {"size": 6.5, "color": "#fff4e8", "bold": True, "wordStyle": {"mode": "reveal", "colour": "#ff8a3d"}}
    shared = client.post("/api/presets/captions/share", json={"name": "Night bus!", "author": "@Ana_B", "style": style})
    assert shared.status_code == 200
    assert 'filename="night-bus-by-ana-b.json"' in shared.headers["content-disposition"]
    manifest = shared.json()
    assert manifest["id"] == "night-bus-by-ana-b" and manifest["author"] == "Ana_B" and manifest["style"] == style
    # the registry takes the file as it is
    monkeypatch.setattr(presets, "COMMUNITY", tmp_path)
    (tmp_path / manifest["id"]).mkdir()
    (tmp_path / manifest["id"] / "manifest.json").write_bytes(shared.content)
    assert [look["id"] for look in presets.community_looks()] == ["night-bus-by-ana-b"]
    # a name formcut's own look has is kept apart; a key the caption track does not take is refused
    assert client.post("/api/presets/captions/share", json={"name": "Rise", "style": style}).json()["id"] == "rise-look"
    refused = client.post("/api/presets/captions/share", json={"name": "x", "style": {"weird": 1}})
    assert refused.status_code == 400 and "does not take" in refused.json()["detail"]


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
