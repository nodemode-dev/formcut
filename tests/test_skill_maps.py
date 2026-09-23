"""The skillset's reference maps list the modules and commands the tree has.

They were written by hand at 0.56.0 and drifted: 40 engine modules unlisted and a
retired one still named. Their inventory sections are generated now.
"""

import subprocess
import sys

from conftest import ROOT


def test_the_generated_map_sections_are_current():
    result = subprocess.run([sys.executable, str(ROOT / "setup" / "skill_maps.py"), "--check"], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout
