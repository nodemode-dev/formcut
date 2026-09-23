"""The curve the Color section draws is the curve the engine applies.

frontend/src/ui/color-section.ts and backend/app/color_grade.py each implement
the same monotone cubic. If they drifted, a colourist would see one curve and
get another. The TypeScript function is lifted from the source and run in Node.
"""

import json
import re
import shutil
import subprocess

import numpy as np
import pytest
from app import color_grade
from conftest import ROOT

CASES = [
    ([[0, 0], [0.25, 0.6], [0.5, 0.62], [1, 1]], False),
    ([[0, 0], [0.3, 0.3], [0.6, 0.3], [1, 0.9]], False),
    ([[0.0, 0.1], [0.3, 0.0], [0.7, -0.05]], True),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node")
def test_the_drawn_curve_is_the_applied_curve():
    source = (ROOT / "frontend" / "src" / "ui" / "color-section.ts").read_text(encoding="utf-8")
    body = re.search(r"export function pchip\((.*?)\n\}\n", source, re.DOTALL).group(0)
    script = re.sub(
        r": number\[\]\[\]|: number\[\]|: boolean|: number", "", body.replace("export ", "").replace("new Array<number>(n)", "new Array(n)")
    )
    grid = np.linspace(0, 1, 41).tolist()
    for points, periodic in CASES:
        run = f"{script}\nconsole.log(JSON.stringify(pchip({json.dumps(points)}, {json.dumps(grid)}, {str(periodic).lower()})));"
        drawn = np.array(json.loads(subprocess.run(["node", "-e", run], capture_output=True, text=True, check=True).stdout))
        xs, ys = np.array([p[0] for p in points], float), np.array([p[1] for p in points], float)
        if periodic:
            xs, ys = np.concatenate([xs - 1, xs, xs + 1]), np.concatenate([ys, ys, ys])
        applied = color_grade._pchip(xs, ys, np.array(grid))
        assert np.allclose(drawn, applied, atol=1e-9), (points, np.abs(drawn - applied).max())
