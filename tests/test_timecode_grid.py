"""The screen, the ruler and the EDL count frames on one grid.

formatTimecode (frontend/src/engine/project.ts) takes the frame index at the
exact rate and labels it as non-drop timecode at the rounded rate. The EDL
export (backend/app/interchange.py _timecode) has to give the same label for
the same time, and the ruler's ticks have to sit on frames whose label ends in
:00, or at 29.97 the two-second tick reads 00:00:01:29. Both TypeScript
functions are lifted from the source and run in Node.
"""

import json
import re
import shutil
import subprocess

import pytest
from app import interchange
from conftest import ROOT

RATES = [24000 / 1001, 30000 / 1001, 60000 / 1001, 24, 25, 30]
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def _lift(name: str) -> str:
    source = (ROOT / "frontend" / "src" / "engine" / "project.ts").read_text(encoding="utf-8")
    found = re.search(rf"export function {name}\(.*?\n\}}\n", source, re.DOTALL)
    assert found, f"{name} is not in project.ts"
    body = found.group(0).replace("export ", "")
    body = re.sub(r"\((\w+): number, (\w+): number\): \w+ \{", r"(\1, \2) {", body)
    return body.replace("(n: number)", "(n)")


def _constant(name: str) -> str:
    source = (ROOT / "frontend" / "src" / "engine" / "project.ts").read_text(encoding="utf-8")
    found = re.search(rf"export const {name} = [^;]+;\n", source)
    assert found, f"{name} is not in project.ts"
    return found.group(0).replace("export ", "")


def _node(script: str):
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


def _times(fps: float) -> list[float]:
    on_grid = [k / fps for k in range(0, 4000, 7)]
    whole = [float(s) for s in range(0, 7300, 13)]
    loose = [(k * 0.6180339887498949 + fps / 97) % 1 * 7200 for k in range(800)]
    return on_grid + whole + loose


@needs_node
@pytest.mark.parametrize("fps", RATES)
def test_the_screen_and_the_edl_give_the_same_timecode(fps):
    times = _times(fps)
    screen = _node(_lift("formatTimecode") + f"console.log(JSON.stringify({json.dumps(times)}.map((t) => formatTimecode(t, {fps!r}))));")
    edl = [interchange._timecode(t, fps) for t in times]
    differ = [(t, a, b) for t, a, b in zip(times, screen, edl, strict=True) if a != b]
    assert not differ, differ[:5]


@needs_node
@pytest.mark.parametrize("fps", RATES)
def test_ruler_ticks_land_on_whole_seconds(fps):
    script = (
        _lift("formatTimecode")
        + _constant("RULER_TICK_SECONDS")
        + _lift("rulerTickTime")
        + f"""
const out = [];
for (let i = 0; i < 1900; i++) out.push(formatTimecode(rulerTickTime(i, {fps!r}), {fps!r}));
console.log(JSON.stringify(out));
"""
    )
    labels = _node(script)
    for index, label in enumerate(labels):
        seconds = index * 2
        assert label == f"{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}:00", (index, label)


def test_the_ruler_places_every_tick_with_rulerTickTime():
    pane = (ROOT / "frontend" / "src" / "ui" / "timeline-pane.ts").read_text(encoding="utf-8")
    ticks = [line for line in pane.splitlines() if 'class="tick"' in line or '".tick"' in line]
    assert ticks
    for line in ticks:
        assert "rulerTickTime" in line or "dataset.t" in line or "data-t=" in line, line
    assert "const t = rulerTickTime(index, fps);" in pane
    assert not re.search(r"const t = i \* 2|t \+= 2|index \* 2 \* PX_PER_SEC", pane)


def _edl_project(fps: float) -> dict:
    clips = [
        {"id": "a", "kind": "video", "label": "a.mp4", "mediaId": "m1", "start": 0.0, "duration": 300 / fps, "sourceIn": 48 / fps},
        {"id": "b", "kind": "video", "label": "a.mp4", "mediaId": "m1", "start": 300 / fps, "duration": 4500 / fps, "sourceIn": 0.0},
        {"id": "c", "kind": "video", "label": "a.mp4", "mediaId": "m1", "start": 4800 / fps, "duration": 11 / fps, "sourceIn": 36000 / fps},
    ]
    return {"fps": fps, "title": "grid", "activeTimeline": 0, "timelines": [{"tracks": [{"clips": clips}]}]}


@pytest.mark.parametrize("fps", RATES)
def test_an_edl_record_starts_at_one_hour_and_comes_back_on_the_same_frames(fps):
    project = _edl_project(fps)
    text, _ = interchange.export_edl(project, 0)
    events = [line.split() for line in text.splitlines() if interchange.EVENT.match(line)]
    assert events[0][6] == "01:00:00:00"
    assert events[0][4] == interchange._timecode(48 / fps, fps)
    timeline, report = interchange.import_edl(text, [{"id": "m1", "name": "a.mp4", "kind": "video"}], fps)
    assert not report
    back = timeline["tracks"][0]["clips"]
    for went, came in zip(project["timelines"][0]["tracks"][0]["clips"], back, strict=True):
        for key in ("start", "duration", "sourceIn"):
            assert round(came[key] * fps) == round(went[key] * fps), (key, went[key], came[key])
