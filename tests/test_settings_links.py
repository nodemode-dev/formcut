"""Dialogs that need something set up link straight to its section in Settings."""

import os
import re

UI = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "ui")


def _read(name):
    with open(os.path.join(UI, name), encoding="utf-8") as handle:
        return handle.read()


def test_the_link_and_the_settings_popout_use_one_event():
    name = re.search(r'new CustomEvent\("([^"]+)"', _read("settings-link.ts")).group(1)
    assert name == "formcut:open-settings"
    assert f'window.addEventListener("{name}"' in _read("settings-popout.ts")


def test_each_dialog_links_to_a_section_that_exists_under_that_title():
    popout = _read("settings-popout.ts")
    assert '["providers", "set.providers"' in popout
    for dialog, section in (("tiktok-dialog.ts", "TikTok"), ("instagram.ts", "Instagram")):
        assert f'openSettings("providers", "{section}")' in _read(dialog), dialog
        assert f'group(providersView, "{section}"' in popout, section
    cloud = _read("cloud.ts")
    assert 'openSettings("providers", LABEL[service])' in cloud
    for label in re.search(r"LABEL: Record<Service, string> = \{([^}]+)\}", cloud).group(1).split(","):
        title = label.split(":")[1].strip().strip('"')
        assert f'group(providersView, "{title}"' in popout, title
