"""The Track workspace (P2 of the planar tracking plan): its markup, styles, strings and the project command that keeps
its layers on the clip, checked always; and, with FORMCUT_BROWSER_TESTS=1 where Chromium and Playwright are present,
the workspace driven in the real app against the engine (the demo opened, its video clip's workspace, a rectangle
drawn, steps and a forward track followed and stopped, the views, the layers saved on the clip)."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "frontend" / "src" / "ui" / "planar-workspace.ts").read_text(encoding="utf-8")


def test_the_workspace_has_its_parts():
    for ref in (
        "layers",
        "add-layer",
        "tools",
        "mode",
        "delete-shape",
        "settings",
        "views",
        "align",
        "img",
        "svg",
        "scrub",
        "strip",
        "back-all",
        "back-one",
        "stop",
        "fwd-one",
        "fwd-all",
        "progress",
        "done",
    ):
        assert f'data-ref="{ref}"' in UI, ref
    assert "/api/planar/track" in UI and "/api/planar/frame/" in UI and "/api/planar/media/" in UI
    assert 'engine.dispatch("clip.planar"' in UI and "if (job) return;" in UI  # saved on the clip; one track at a time
    css = (ROOT / "frontend" / "src" / "styles" / "app.css").read_text(encoding="utf-8")
    assert ".pw { position: fixed; inset: 0; z-index: var(--z-viewer);" in css
    inspector = (ROOT / "frontend" / "src" / "ui" / "inspector-pane.ts").read_text(encoding="utf-8")
    assert 'data-ref="planar-btn"' in inspector


def test_the_project_keeps_the_layers_on_the_clip():
    project = (ROOT / "frontend" / "src" / "engine" / "project.ts").read_text(encoding="utf-8")
    assert 'case "clip.planar":' in project and "found.clip.planar = structuredClone(p.planar)" in project
    types = (ROOT / "frontend" / "src" / "engine" / "types.ts").read_text(encoding="utf-8")
    assert "planar?: ClipPlanar;" in types and "export interface PlanarLayer" in types


def test_every_string_the_workspace_uses_is_in_every_language():
    keys = set(
        re.findall(r't\("(planar\.[a-zA-Z.]+)"\)', UI + (ROOT / "frontend" / "src" / "ui" / "tracking.ts").read_text(encoding="utf-8"))
    )
    keys |= {f"planar.view.{v}" for v in ("surface", "grid", "trace", "matte", "stabilise")}
    keys |= {f"planar.motion.{m}" for m in ("translation", "scale", "rotation", "shear", "perspective")} | {
        f"planar.mode.{m}" for m in ("large", "small", "manual")
    }
    english = json.loads((ROOT / "frontend" / "src" / "i18n" / "en.json").read_text(encoding="utf-8"))
    pack = (ROOT / "frontend" / "src" / "i18n" / "language-pack.ts").read_text(encoding="utf-8")
    for lang in ("de.json", "es.json"):
        other = json.loads((ROOT / "frontend" / "src" / "i18n" / lang).read_text(encoding="utf-8"))
        assert keys <= set(other), (lang, sorted(keys - set(other)))
    for lang in ("ar", "fa", "he", "hr"):
        other = json.loads((ROOT / "frontend" / "public" / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
        assert keys <= set(other), (lang, sorted(keys - set(other)))
    missing = [k for k in keys if k not in english or f"\n{english[k]}|" not in pack]
    assert not missing, missing  # the nine languages the pack carries, by the English text


@pytest.mark.skipif(
    os.environ.get("FORMCUT_BROWSER_TESTS") != "1", reason="the browser run: FORMCUT_BROWSER_TESTS=1 with Chromium and Playwright"
)
def test_the_workspace_in_the_real_app(tmp_path):
    playwright = pytest.importorskip("playwright.sync_api")
    dist = ROOT / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        pytest.skip("build the interface first")
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    env = {**os.environ, "FORMCUT_DATA_DIR": str(tmp_path), "FORMCUT_NO_WARM": "1", "FORMCUT_DIST": str(dist)}
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT / "backend",
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    errors: list[str] = []
    try:
        for _ in range(200):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1)  # noqa: S310 - the test's own local engine
                break
            except OSError:
                time.sleep(0.2)
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(base + "/")
            time.sleep(3)
            if page.locator(".mode-ask:not([hidden])").count():
                page.locator(".mode-ask:not([hidden]) button", has_text="Advanced").first.click()
                time.sleep(1.5)
            page.click('[data-act="demo"]', timeout=20000)
            page.wait_for_selector(".clip.k-video", timeout=60000)
            # the demo's picture dragged to the timeline's start, so it is on screen at the frames tracked below (the
            # demo's video shows its media from 2 s at timeline 0; its swirl loses the plane within a dozen frames)
            title = page.locator(".clip.k-image").first.bounding_box()
            page.mouse.move(title["x"] + title["width"] / 2, title["y"] + title["height"] / 2)
            page.mouse.down()
            page.mouse.move(title["x"] - 600, title["y"] + title["height"] / 2, steps=10)
            page.mouse.up()
            time.sleep(0.5)
            page.locator(".clip.k-video").first.click()
            page.wait_for_selector('[data-ref="planar-btn"]', state="attached", timeout=10000)
            for tab in ("animation", "adjust", "speed", "repair"):
                if page.locator('[data-ref="planar-btn"]').first.is_visible():
                    break
                page.locator(f'[data-tab="{tab}"]').first.click()
                time.sleep(0.5)
            page.click('[data-ref="planar-btn"]')
            page.wait_for_function(
                "() => { const i = document.querySelector('.pw [data-ref=img]'); return i && i.complete && i.naturalWidth > 0 }",
                timeout=30000,
            )
            page.click('.pw [data-tool="rect"]')
            box = page.locator(".pw [data-ref=svg]").bounding_box()
            x0, y0, x1, y1 = (
                box["x"] + box["width"] * 0.35,
                box["y"] + box["height"] * 0.3,
                box["x"] + box["width"] * 0.65,
                box["y"] + box["height"] * 0.7,
            )
            page.mouse.move(x0, y0)
            page.mouse.down()
            page.mouse.move((x0 + x1) / 2, (y0 + y1) / 2)
            page.mouse.move(x1, y1)
            page.mouse.up()
            assert page.locator(".pw .pw-layer").count() == 1
            frame = lambda: int(re.sub(r"[^0-9]", "", page.inner_text(".pw [data-ref=frame]")))  # noqa: E731
            start = frame()
            page.click('.pw [data-ref="fwd-one"]')
            page.wait_for_function(
                "b => Number(document.querySelector('.pw [data-ref=frame]').textContent.replace(/[^0-9]/g, '')) > b && document.querySelector('.pw [data-ref=stop]').disabled",
                arg=start,
                timeout=60000,
            )
            page.click('.pw [data-ref="fwd-all"]')
            page.wait_for_function(
                "b => Number(document.querySelector('.pw [data-ref=frame]').textContent.replace(/[^0-9]/g, '')) >= b + 3",
                arg=start,
                timeout=150000,
            )
            page.click('.pw [data-ref="stop"]')
            page.wait_for_function("() => document.querySelector('.pw [data-ref=stop]').disabled", timeout=60000)
            assert frame() >= start + 3
            for view in ("grid", "trace", "stabilise"):
                page.click(f'.pw [data-view="{view}"]')
            assert page.locator(".pw svg .pw-grid").count() > 0 and page.locator(".pw svg .pw-trace").count() == 4
            assert "matrix3d" in page.eval_on_selector(".pw [data-ref=inner]", "e => e.style.transform")
            shots = os.environ.get("FORMCUT_BROWSER_SHOTS")
            # P3: the track applied to another of the demo's clips as a corner pin
            # the picture, now at the timeline's start, is on screen at the tracked frames
            targets = page.eval_on_selector_all('.pw [data-ref="target"] option', "els => els.map(e => [e.value, e.textContent])")
            title = next((value for value, text in targets if "effect-example-image" in text), None)
            assert title, targets
            page.select_option('.pw [data-ref="target"]', title)
            page.select_option('.pw [data-ref="kind"]', "corner-pin")
            before = page.inner_text(".pw [data-ref=status]")
            page.click('.pw [data-ref="apply"]')
            page.wait_for_function("b => document.querySelector('.pw [data-ref=status]').textContent !== b", arg=before, timeout=30000)
            assert "Applied" in page.inner_text(".pw [data-ref=status]"), page.inner_text(".pw [data-ref=status]")
            # and the tracked clip's own layers as its matte
            page.select_option('.pw [data-ref="kind"]', "matte")
            before = page.inner_text(".pw [data-ref=status]")
            page.click('.pw [data-ref="apply"]')
            page.wait_for_function("b => document.querySelector('.pw [data-ref=status]').textContent !== b", arg=before, timeout=10000)
            assert "Matte" in page.inner_text(".pw [data-ref=status]"), page.inner_text(".pw [data-ref=status]")
            if shots:
                page.screenshot(path=f"{shots}/workspace.png")
            page.click('.pw [data-ref="done"]')
            page.wait_for_selector(".pw", state="detached", timeout=5000)
            time.sleep(3)
            if shots:
                page.screenshot(path=f"{shots}/editor.png")
                # a second in, where the demo's picture has faded in (its fade-in is half a second); the pin holds its
                # last tracked corners past the tracked frames. The sandbox's one core takes seconds for a new frame.
                for _ in range(30):
                    page.keyboard.press("ArrowRight")
                time.sleep(8)
                page.screenshot(path=f"{shots}/editor-1s.png")
            browser.close()
        saved = []
        listing = json.loads(urllib.request.urlopen(base + "/api/projects").read())  # noqa: S310 - the test's own local engine
        for summary in listing if isinstance(listing, list) else listing.get("projects", []):
            doc = json.loads(urllib.request.urlopen(f"{base}/api/projects/{summary['id']}").read())  # noqa: S310 - the test's own local engine
            saved += [
                c["planar"]
                for tl in doc.get("timelines", [])
                for tr in tl.get("tracks", [])
                for c in tr.get("clips", [])
                if c.get("planar")
            ]
        assert saved and saved[0]["version"] == 1 and len(saved[0]["layers"]) == 1 and saved[0]["layers"][0]["surface"]
        pins = [
            c["cornerPin"]
            for tl in doc.get("timelines", [])
            for tr in tl.get("tracks", [])
            for c in tr.get("clips", [])
            if c.get("cornerPin")
        ]
        assert pins and len(pins[0]["times"]) == len(pins[0]["points"]) > 0 and len(pins[0]["points"][0]) == 8
        mattes = [
            c["planarMatte"]
            for tl in doc.get("timelines", [])
            for tr in tl.get("tracks", [])
            for c in tr.get("clips", [])
            if c.get("planarMatte")
        ]
        assert mattes and mattes[0]["layers"] and mattes[0]["feather"] == 2 and mattes[0]["invert"] is False
        assert not errors, errors
    finally:
        server.terminate()
