"""The MCP server hands back the clip ids that per-clip edits need.

Every per-clip operation in formcut_edit (crossfade, trim, move, remove) takes a
clip id, and neither formcut_add_clip nor formcut_get_project returned one, so an
agent asked to crossfade the clips it had just placed could not do it.
"""

from __future__ import annotations

import pytest

agent_mcp = pytest.importorskip("app.agent_mcp")

PROJECT = {
    "title": "Launch teaser",
    "revision": 4,
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "duration": 4.0,
    "activeTimeline": 0,
    "timelines": [
        {
            "tracks": [
                {
                    "name": "Video",
                    "clips": [
                        {"id": "a1b2c3d4", "label": "hero.png", "mediaId": "m1", "start": 0, "duration": 2},
                        {"id": "e5f6a7b8", "label": "cut.png", "mediaId": "m2", "start": 2, "duration": 2},
                    ],
                }
            ]
        }
    ],
}


def test_get_project_lists_each_clip_id(monkeypatch):
    monkeypatch.setattr(agent_mcp, "_rpc", lambda method, params=None, identify=True: (True, PROJECT))
    reply = agent_mcp.formcut_get_project("p1")
    assert "[clip a1b2c3d4]" in reply
    assert "[clip e5f6a7b8]" in reply


def test_add_clip_returns_the_id_it_sent(monkeypatch):
    sent = []

    def rpc(method, params=None, identify=True):
        if method == "media.list":
            return True, [{"id": "m1", "kind": "image", "name": "hero.png"}]
        sent.append(params["commands"][0]["clip"]["id"])
        return True, {"revision": 5, "duration": 2.0}

    monkeypatch.setattr(agent_mcp, "_rpc", rpc)
    reply = agent_mcp.formcut_add_clip("p1", 4, "m1", start=0, duration=2)
    assert sent and f"as clip {sent[0]} " in reply
    assert "revision 5" in reply
