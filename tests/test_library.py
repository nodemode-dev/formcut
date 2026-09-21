"""The library: stickers, music and sound effects made by formcut's own code."""

import json
import wave
from pathlib import Path

import numpy as np
import pytest
from app import library
from app.main import app
from fastapi.testclient import TestClient
from PIL import Image

client = TestClient(app, headers={"x-formcut-local": "1"})
I18N = Path(__file__).resolve().parents[1] / "frontend" / "src" / "i18n"


@pytest.fixture
def shelf(tmp_path, monkeypatch):
    monkeypatch.setattr(library, "LIBRARY_DIR", tmp_path / "library")
    return tmp_path / "library"


def test_the_catalogue_lists_every_kind():
    counts = {kind: len(client.get(f"/api/library/{kind}").json()["items"]) for kind in library.KINDS}
    assert counts == {"stickers": 32, "sounds": 17, "music": 6}


def test_ids_are_unique_and_urls_point_at_their_files():
    for kind, items in library.KINDS.items():
        ids = [item.id for item in items]
        assert len(ids) == len(set(ids)), kind
        listed = client.get(f"/api/library/{kind}").json()
        assert listed["licence"] == library.LICENCE
        assert all(entry["url"] == f"/api/library/{kind}/{entry['id']}/file" for entry in listed["items"])


def test_an_unknown_kind_or_item_is_not_found():
    assert client.get("/api/library/fonts").status_code == 404
    assert client.get("/api/library/stickers/unicorn/file").status_code == 404


def test_a_sticker_is_a_transparent_square_with_art_in_the_middle(shelf):
    image = Image.open(library.render("stickers", "star"))
    assert image.mode == "RGBA" and image.size == (library.SIZE, library.SIZE)
    alpha = np.asarray(image)[:, :, 3]
    assert alpha[0, 0] == 0 and alpha[-1, -1] < 40
    assert alpha[library.SIZE // 2, library.SIZE // 2] == 255


def test_every_sticker_renders(shelf):
    for item in library.STICKERS:
        assert Image.open(library.render("stickers", item.id)).size == (library.SIZE, library.SIZE), item.id


def test_rendering_is_deterministic(shelf):
    first = library.render("stickers", "new").read_bytes()
    sound = library.render("sounds", "whoosh").read_bytes()
    for path in shelf.glob("*/*.*"):
        path.unlink()
    assert library.render("stickers", "new").read_bytes() == first
    assert library.render("sounds", "whoosh").read_bytes() == sound


def test_every_sound_has_its_length_and_headroom(shelf):
    for item in library.SOUNDS:
        with wave.open(str(library.render("sounds", item.id))) as audio:
            assert (audio.getnchannels(), audio.getframerate()) == (1, library.SOUND_RATE), item.id
            assert abs(audio.getnframes() / audio.getframerate() - item.seconds) < 0.001, item.id
            samples = np.frombuffer(audio.readframes(audio.getnframes()), "<i2") / 32767
        assert 0.5 < np.abs(samples).max() <= 0.9, item.id


def test_a_track_lasts_its_bars_and_rings_on(shelf):
    item = library.find("music", "low-tide")
    path = library.render("music", "low-tide")
    assert path.suffix in (".m4a", ".wav")
    assert item.seconds == pytest.approx(8 * 4 * 60 / 60 + library.TAIL)
    audio = library.MUSIC[2].make()
    assert audio.shape == (round(item.seconds * library.MUSIC_RATE), 2)
    assert 0.85 < np.abs(audio).max() <= 0.9


def test_a_changed_version_renders_again(shelf, monkeypatch):
    path = library.render("stickers", "heart")
    path.write_bytes(b"stale")
    monkeypatch.setattr(library, "VERSION", "next")
    fresh = library.render("stickers", "heart")
    assert fresh.read_bytes() != b"stale"
    assert (shelf / "stickers" / ".version").read_text() == "next"


def test_importing_puts_a_copy_in_the_media_bin(shelf):
    record = client.post("/api/library/stickers/crown/import").json()
    assert record["kind"] == "image" and record["name"] == "Crown"
    assert record["licence"] == library.LICENCE
    assert library.render("stickers", "crown").exists()
    sound = client.post("/api/library/sounds/pop/import").json()
    assert sound["kind"] == "audio" and sound["name"] == "Pop"


def test_every_label_the_view_shows_is_translated():
    english = json.loads((I18N / "en.json").read_text(encoding="utf-8"))
    rows = (I18N / "language-pack.ts").read_text(encoding="utf-8").split("`")[1].splitlines()
    packed = {row.split("|")[0] for row in rows if row}
    keys = [
        "tab.stickers",
        "tab.music",
        "tab.sounds",
        "library.add",
        "library.added",
        "library.play",
        "library.stop",
        "library.preparing",
        "library.licence",
    ]
    keys += [f"library.cat.{item.category}" for items in library.KINDS.values() for item in items]
    keys += [f"library.sound.{item.id}" for item in library.SOUNDS]
    for code in ("en", "de", "es"):
        strings = json.loads((I18N / f"{code}.json").read_text(encoding="utf-8"))
        assert not [key for key in keys if key not in strings], code
    assert not [english[key] for key in keys if english[key] not in packed]
