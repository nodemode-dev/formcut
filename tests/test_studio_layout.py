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


def test_the_generator_has_steps_and_seed_sliders_continuous_and_a_viewer():
    for marker in (
        'data-gen-steps="${kind}"',
        'type="range" min="-1" max="4294967295"',
        'data-gen-continuous="${kind}"',
        'data-gen-view="${item.id}"',
    ):
        assert marker in SOURCE, marker
    # the viewer is the platform's own now (viewer.ts), the generator's results among its users
    assert "gen-viewer" in (ROOT / "ui" / "viewer.ts").read_text(encoding="utf-8") and "openViewer(" in SOURCE
    tokens = (ROOT / "styles" / "tokens.css").read_text(encoding="utf-8")
    assert "--z-viewer: 750;" in tokens


def test_results_are_a_gallery_of_pictures_with_their_line_on_hover():
    assert 'class="gen-gallery" data-gen-grid="${kind}"' in SOURCE and 'class="gen-tile' in SOURCE and 'class="gen-tile-bar"' in SOURCE
    assert "data-gen-to-media" in SOURCE and "data-gen-delete" in SOURCE and "/api/generative?kind=" in SOURCE
    css = (ROOT / "styles" / "app.css").read_text(encoding="utf-8")
    assert (
        ".gen-tile { position: relative; aspect-ratio: 1;" in css
        and ".gen-tile-bar span { flex: 1; min-width: 0; white-space: nowrap;" in css
    )
    assert 'data-gen-wrap-load="${kind}"' in SOURCE and "/api/generate/prompt-wrap" in SOURCE


def test_a_wrap_needs_no_prompt_and_generate_needs_one():
    """2.3.1 let Generate run a wrap by slipping its first entry into the prompt box; 2.3.2 makes the wrap its own run.
    Run wrap asks for a loaded wrap and a model that runs one, and no prompt; Generate still asks for its prompt."""
    head = SOURCE[SOURCE.index("const go = (mode") :]
    check = head.index('t("gen.needprompt")')
    assert (
        "if (!wrapMode && !prompt)" in head[: check + 40] and 't("gen.wrap.none")' in head[:check] and 't("gen.wrap.krea")' in head[:check]
    )


def test_the_prompt_wrap_is_its_own_run_in_its_own_section():
    assert (
        'data-gen-wrap-section="${kind}"' in SOURCE and 'data-gen-wrap-go="${kind}"' in SOURCE and 'data-gen-wrap-loop="${kind}"' in SOURCE
    )
    assert '"/api/generate/wrap-run"' in SOURCE and 'go("wrap")' in SOURCE and 'go("panel")' in SOURCE
    assert "body.options.wrap" not in SOURCE and "firstOfWrap" not in SOURCE  # Generate sends no wrap, and no stand-in prompt
