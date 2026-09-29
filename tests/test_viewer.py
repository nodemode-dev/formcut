"""One full-screen viewer for the platform (viewer.ts): the Studio generator's results, the media library's cards (View,
or Space on a focused card) and the start screen's media all open it; it shows pictures and videos, above everything
(--z-viewer), Escape or a click to close, the arrows through the rest."""

from __future__ import annotations

from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "frontend" / "src" / "ui"


def test_one_viewer_everywhere():
    viewer = (UI / "viewer.ts").read_text(encoding="utf-8")
    assert "export function openViewer" in viewer and "gen-viewer-video" in viewer and "ArrowRight" in viewer and "Escape" in viewer
    for name in ("studio-tools.ts", "media-pane.ts", "start-screen.ts"):
        source = (UI / name).read_text(encoding="utf-8")
        assert 'from "./viewer"' in source and "openViewer(" in source, name
    studio = (UI / "studio-tools.ts").read_text(encoding="utf-8")
    assert 'document.createElement("div");\n  viewer.className = "gen-viewer"' not in studio  # the generator's own copy is gone
    library = (UI / "media-pane.ts").read_text(encoding="utf-8")
    assert 'class="bin-view"' in library and 'ev.key === " "' in library and "card.tabIndex = 0" in library


def test_stop_does_not_redraw_the_bar_and_a_picture_done_leaves_it():
    studio = (UI / "studio-tools.ts").read_text(encoding="utf-8")
    assert studio.count("if (controller.signal.aborted) break;") >= 2
    generate = (Path(__file__).resolve().parents[1] / "backend" / "app" / "generate.py").read_text(encoding="utf-8")
    assert 'report(None, "Next picture"' in generate and "report(0.1," not in generate
