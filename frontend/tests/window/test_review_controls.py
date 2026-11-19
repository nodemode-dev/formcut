"""The built window, driven as a person would: a 100 fps project from the format sheet, Make proxy on a media card,
and the Proxies switch and size in Settings, each read back from the engine rather than from the page.

The engine is the one test_window.py starts, on an empty data folder. A clip is uploaded before the window opens so
its card is in the bin; it is MPEG-4 Part 2, which every ffmpeg build encodes, so the proxy really builds.
"""

import shutil
import subprocess

import pytest
from test_window import engine  # noqa: F401 - the fixture, shared with the smoke test

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs ffmpeg to make a clip")
TIMEOUT = 60_000


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    path = tmp_path_factory.mktemp("review-controls") / "clip.mp4"
    command = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=25:duration=1", "-c:v", "mpeg4", str(path)]
    subprocess.run(command, check=True)
    return path


@pytest.fixture
def window(engine, clip):  # noqa: F811 - the imported fixture
    from playwright.sync_api import sync_playwright

    errors = []
    with sync_playwright() as p:
        claim = p.request.new_context(base_url=engine, extra_http_headers={"x-formcut-local": "1"})
        key = claim.post("/api/window/key").json()["key"]
        claim.dispose()
        api = p.request.new_context(base_url=engine, extra_http_headers={"x-formcut-local": "1", "x-formcut-window-key": key})
        uploaded = api.post("/api/media", multipart={"file": {"name": "clip.mp4", "mimeType": "video/mp4", "buffer": clip.read_bytes()}})
        assert uploaded.ok, uploaded.text()
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.add_init_script(f"sessionStorage.setItem('formcut-window-key', {key!r})")
        page.goto(engine + "/", wait_until="load", timeout=120_000)
        page.click(".mode-ask [data-later]", timeout=TIMEOUT)
        page.click('[data-act="new"]', timeout=TIMEOUT)
        yield page, api, uploaded.json()["id"], errors
        browser.close()
        api.dispose()


@pytest.mark.parametrize(("label", "rate"), [("100", "100"), ("29.97", str(30000 / 1001)), ("119.88", str(120000 / 1001))])
def test_a_project_made_at_a_high_or_ntsc_rate_previews_at_it(window, label, rate):
    page, _, _, errors = window
    button = f'.format-sheet [data-fps="{rate}"]'
    assert page.text_content(button) == label
    page.click(button)
    assert page.get_attribute(button, "class") == "is-active"
    page.click('[data-ref="format-create"]')
    page.wait_for_function("() => document.querySelector('.start-overlay').hidden", timeout=TIMEOUT)
    page.wait_for_function(f"() => document.querySelector('[data-ref=\"meta\"]').textContent.includes('· {label} fps')", timeout=TIMEOUT)
    assert not errors, errors


def test_make_proxy_on_a_card_builds_one_and_offers_a_rebuild(window):
    page, api, media_id, errors = window
    page.click('[data-ref="format-create"]')
    page.wait_for_function("() => document.querySelector('.start-overlay').hidden", timeout=TIMEOUT)
    page.click('[data-tab="Media"]')
    button = page.locator(f'[data-proxy-action="{media_id}"]')
    assert button.get_attribute("title") == "Make proxy"
    with page.expect_response(lambda r: r.url.endswith(f"/api/media/{media_id}/proxy") and r.request.method == "POST") as sent:
        page.hover(f'.bin-card[data-media="{media_id}"]')
        button.click()
    assert sent.value.status == 202
    page.wait_for_function(
        f"() => document.querySelector('[data-proxy=\"{media_id}\"]').dataset.state === 'ready'", timeout=TIMEOUT, polling=500
    )
    assert api.get(f"/api/media/{media_id}/proxy").json()["state"] == "ready"
    assert button.get_attribute("title") == "Rebuild proxy"
    assert not button.is_disabled()
    assert not errors, errors


def test_the_proxies_switch_and_size_in_settings_reach_the_engine(window):
    page, api, _, errors = window
    page.click('[data-ref="format-create"]')
    page.wait_for_function("() => document.querySelector('.start-overlay').hidden", timeout=TIMEOUT)
    page.click('[data-ref="settings"]')
    page.click('.set-tab[data-page="playback"]')
    box, size = page.locator("[data-proxy-enabled]"), page.locator("[data-proxy-size]")
    page.wait_for_function("() => document.querySelector('[data-proxy-size]').options.length === 3", timeout=TIMEOUT)
    assert box.is_checked()
    assert size.input_value() == "1280"
    try:
        with page.expect_response(lambda r: r.url.endswith("/api/proxies/settings") and r.request.method == "POST"):
            box.uncheck()
        with page.expect_response(lambda r: r.url.endswith("/api/proxies/settings") and r.request.method == "POST"):
            size.select_option("1920")
        assert api.get("/api/proxies/settings").json() == {"enabled": False, "size": 1920, "sizes": [960, 1280, 1920]}
    finally:
        restored = api.post("/api/proxies/settings", data={"enabled": True, "size": 1280})
    assert restored.ok, restored.text()
    assert not errors, errors
