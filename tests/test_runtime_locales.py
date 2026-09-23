"""The locales that ship as files (frontend/public/locales): Arabic, Persian,
Hebrew and Croatian. Each carries every English string, so none falls back to
English; placeholders match; each is in its own script, and Persian uses its own
yeh and kaf (Arabic's are the classic sign of machine output)."""

import json
import re

import pytest
from conftest import ROOT

EN = json.loads((ROOT / "frontend" / "src" / "i18n" / "en.json").read_text(encoding="utf-8"))
FILES = sorted((ROOT / "frontend" / "public" / "locales").glob("*.json"))
HOLDER = re.compile(r"\{[a-zA-Z0-9_]+\}")
SCRIPT = {"ar": r"[\u0600-\u06FF]", "fa": r"[\u0600-\u06FF]", "he": r"[\u0590-\u05FF]"}


def test_the_four_ship():
    assert {path.stem for path in FILES} >= {"ar", "fa", "he", "hr"}


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.stem)
def test_every_string_is_translated_with_its_placeholders(path):
    strings = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in EN if not strings.get(key, "").strip()]
    assert not missing, f"{path.stem} lacks {len(missing)}: {missing[:8]}"
    for key, english in EN.items():
        assert sorted(HOLDER.findall(strings[key])) == sorted(HOLDER.findall(english)), (path.stem, key)
        assert "\u2014" not in strings[key] and "\u2013" not in strings[key], (path.stem, key)
    assert strings["language.name"].strip()


@pytest.mark.parametrize("code", ["ar", "fa", "he"])
def test_each_is_in_its_own_script(code):
    strings = json.loads((ROOT / "frontend" / "public" / "locales" / f"{code}.json").read_text(encoding="utf-8"))
    written = [value for key, value in strings.items() if key in EN and re.search(r"[a-z]{4,}", EN[key]) and value != EN[key]]
    in_script = [value for value in written if re.search(SCRIPT[code], value)]
    assert len(in_script) == len(written), [value for value in written if value not in in_script][:5]
    if code == "fa":
        assert not [value for value in strings.values() if re.search("[يك]", value)], "Persian writes ی and ک"
    if code == "ar":
        assert not [value for value in strings.values() if re.search("[پچژگیک]", value)], "no Persian-only letters in Arabic"


@pytest.mark.parametrize("path", FILES, ids=lambda path: path.stem)
def test_every_phrase_the_pack_translates_by_its_wording_is_there_too(path):
    """385 phrases are translated by their English wording (language-pack.ts), not by
    key; without phrase: entries they stayed English in these locales."""
    body = (ROOT / "frontend" / "src" / "i18n" / "language-pack.ts").read_text(encoding="utf-8").split("`")[1]
    wording = [line.split("|")[0] for line in body.splitlines() if line.strip()]
    strings = json.loads(path.read_text(encoding="utf-8"))
    missing = [source for source in wording if source not in set(EN.values()) and not strings.get(f"phrase:{source}", "").strip()]
    assert not missing, f"{path.stem} lacks {len(missing)} phrases: {missing[:8]}"
