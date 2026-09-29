"""Studio's Local models page holds its model cards: the FLUX.2 [klein] 4B card and the checkpoints panel sat after
the page's section in 2.0.7 to 2.0.11, so they were drawn on every Studio page; and the cards' words go through the
translations, as every string in the interface does."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend" / "src"
SOURCE = (ROOT / "ui" / "studio-tools.ts").read_text(encoding="utf-8")


def test_the_model_cards_are_inside_local_models():
    start = SOURCE.index('data-view="models"')
    end = SOURCE.index("</section>", start)
    for marker in ("data-krea-card", "data-klein-card", "data-ckpt-card"):
        assert start < SOURCE.index(marker) < end, marker


def test_the_cards_words_are_translated():
    english = json.loads((ROOT / "i18n" / "en.json").read_text(encoding="utf-8"))
    used = set(re.findall(r't\("(models\.[\w.]+)"\)', SOURCE))
    assert len(used) >= 25 and used <= set(english)
    for card in ("data-krea-card", "data-klein-card", "data-ckpt-card"):
        block = SOURCE[SOURCE.index(card) : SOURCE.index("</div>\n      </div>", SOURCE.index(card))]
        assert "Install Krea 2<" not in block and "Not installed<" not in block and ">Build <" not in block
