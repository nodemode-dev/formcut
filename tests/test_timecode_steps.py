"""A frame step moves the timecode by exactly one frame, at every frame rate.

frontend/src/engine/project.ts steps the playhead on the exact frame grid
(`floor(playhead * fps + 1e-6) + n`, divided back by fps). The timecode has to
count frames on that same grid: counted at the rounded rate, 29.97, 23.976 and
59.94 fps showed a two-frame jump about once every thousand steps. Both
functions are lifted from the source and run in Node.
"""

import json
import re
import shutil
import subprocess

import pytest
from conftest import ROOT

RATES = [24, 25, 30, 60, 24000 / 1001, 30000 / 1001, 60000 / 1001]
STEPS = 18000


def _lifted() -> str:
    source = (ROOT / "frontend" / "src" / "engine" / "project.ts").read_text(encoding="utf-8")
    timecode = re.search(r"export function formatTimecode\(.*?\n\}\n", source, re.DOTALL).group(0)
    timecode = timecode.replace("export ", "").replace("seconds: number, fps: number): string", "seconds, fps)")
    timecode = timecode.replace("(n: number)", "(n)")
    step = re.search(r'case "transport\.step":\s*\n\s*(s\.playhead = .*?;)\n', source).group(1).replace(" as number", "")
    return f"{timecode}\nfunction step(s, payload) {{ {step} }}\n"


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
@pytest.mark.parametrize("fps", RATES)
def test_each_frame_step_moves_the_timecode_by_one_frame(fps):
    run = (
        _lifted()
        + f"""
const fps = {fps!r}, rate = Math.max(1, Math.round(fps)), s = {{playhead: 0, fps, duration: 1e9}};
const count = (tc) => tc.split(":").map(Number).reduce((a, v, i) => a + v * [3600 * rate, 60 * rate, rate, 1][i], 0);
let previous = count(formatTimecode(0, fps)), bad = [];
for (let i = 1; i <= {STEPS}; i++) {{
  step(s, 1);
  const now = count(formatTimecode(s.playhead, fps));
  if (now - previous !== 1) bad.push([i, now - previous]);
  previous = now;
}}
for (let i = {STEPS} - 1; i >= 0; i--) {{
  step(s, -1);
  const now = count(formatTimecode(s.playhead, fps));
  if (previous - now !== 1) bad.push([-i, previous - now]);
  previous = now;
}}
console.log(JSON.stringify({{bad: bad.slice(0, 5), total: bad.length, end: formatTimecode(s.playhead, fps)}}));
"""
    )
    out = json.loads(subprocess.run(["node", "-e", run], capture_output=True, text=True, check=True).stdout)
    assert out["total"] == 0, out
    assert out["end"] == "00:00:00:00", out


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_whole_seconds_still_read_as_whole_seconds_at_integer_rates():
    run = _lifted() + "console.log(JSON.stringify([formatTimecode(1.2, 30), formatTimecode(4.1, 30), formatTimecode(3723.5, 25)]));"
    out = json.loads(subprocess.run(["node", "-e", run], capture_output=True, text=True, check=True).stdout)
    assert out == ["00:00:01:06", "00:00:04:03", "01:02:03:12"]
