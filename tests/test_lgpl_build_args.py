import re

from conftest import ROOT


def test_the_windows_batch_passes_every_argument_the_ffmpeg_script_needs():
    bat = (ROOT / "setup" / "build_lgpl_av.bat").read_text(encoding="utf-8")
    line = next(l for l in bat.splitlines() if "build_lgpl_ffmpeg_msvc" in l)
    call = line.split('build_lgpl_ffmpeg_msvc"', 1)[1].split("||", 1)[0]
    script = (ROOT / "setup" / "build_lgpl_ffmpeg_msvc").read_text(encoding="utf-8")
    wanted = max(int(n) for n in re.findall(r"\$\{(\d):\?", script))
    assert '""' not in call
    assert len(re.findall(r'"[^"]*"', call)) == wanted
