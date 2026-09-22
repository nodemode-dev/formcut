"""The demo media: present, credited, and long enough for the demo timeline.

The four files are tracked in examples/demo with their sources and licences in its
README. The demo project (frontend/src/engine/demo.ts) plays each footage clip from
a source offset; when the media changed to 10-second clips, the second clip still
started 42 seconds in, past its end.
"""

import json
import re
import shutil
import subprocess

import pytest
from app.demo import FILES
from conftest import ROOT

DEMO = ROOT / "examples" / "demo"


def test_every_demo_file_is_present_and_credited():
    credits = (DEMO / "README.md").read_text(encoding="utf-8")
    for name in FILES:
        assert (DEMO / name).is_file(), name
        assert f"`{name}`" in credits, f"{name} has no credit in examples/demo/README.md"


@pytest.mark.skipif(shutil.which("ffprobe") is None, reason="needs ffprobe")
def test_each_footage_clip_fits_inside_its_video():
    source = (ROOT / "frontend" / "src" / "engine" / "demo.ts").read_text(encoding="utf-8")
    files = dict(re.findall(r'const (\w+) = byName\("([^"]+\.mp4)"\)', source))
    placed = re.findall(r"place\((\w+), [\d.]+, ([\d.]+), \{ sourceIn: ([\d.]+)", source)
    assert {name for name, _, _ in placed} == set(files)
    for name, duration, offset in placed:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(DEMO / files[name])],
            capture_output=True,
            text=True,
            check=True,
        )
        length = float(json.loads(probe.stdout)["format"]["duration"])
        assert float(offset) + float(duration) <= length + 0.01, (
            f"{files[name]} is {length:.1f}s; the demo plays {offset}s to {float(offset) + float(duration)}s"
        )
