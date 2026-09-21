"""The export dialog names the encoder in use and warns when MP4 can only be MPEG-4 Part 2."""

import json
import os

from app.main import app
from fastapi.testclient import TestClient

FOLDER = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "i18n")


def _read(name):
    with open(os.path.join(FOLDER, name), encoding="utf-8") as handle:
        return handle.read()


def test_the_encoder_note_and_the_mpeg4_warning_are_translated_with_their_placeholders():
    english = json.loads(_read("en.json"))
    rows = _read("language-pack.ts").split("`")[1].splitlines()
    packed = {row.split("|")[0]: row.split("|")[1:] for row in rows if row}
    for key, marks in (("export.encoderUses", ("{codec}", "{encoder}")), ("export.mpeg4Warning", ())):
        for code in ("de", "es"):
            text = json.loads(_read(f"{code}.json"))[key]
            assert all(mark in text for mark in marks), (code, key)
        assert english[key] in packed, key
        assert all(all(mark in text for mark in marks) for text in packed[english[key]]), key


def test_the_status_names_an_encoder_for_every_codec_mp4_offers():
    encoders = TestClient(app).get("/api/render/status").json()["encoders"]
    offered = encoders["containers"]["mp4"]
    assert offered, "MP4 always has at least MPEG-4 Part 2"
    assert all(encoders["codecs"][codec]["encoder"] for codec in offered)
    assert offered[-1] == "mpeg4" or "mpeg4" not in offered
