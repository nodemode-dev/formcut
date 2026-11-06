import re

from conftest import ROOT


def test_the_windows_batch_passes_every_argument_the_ffmpeg_script_needs():
    bat = (ROOT / "setup" / "build_lgpl_av.bat").read_text(encoding="utf-8")
    line = next(row for row in bat.splitlines() if "build_lgpl_ffmpeg_msvc" in row)
    call = line.split('build_lgpl_ffmpeg_msvc"', 1)[1].split("||", 1)[0]
    script = (ROOT / "setup" / "build_lgpl_ffmpeg_msvc").read_text(encoding="utf-8")
    wanted = max(int(n) for n in re.findall(r"\$\{(\d):\?", script))
    assert '""' not in call
    assert len(re.findall(r'"[^"]*"', call)) == wanted


def test_the_unix_build_installs_nasm_for_x86_and_shows_configure_errors():
    """Intel Macs (GitHub's macos-15-intel) have no nasm, which FFmpeg needs for its x86 SIMD paths; the 2.12.2 Intel
    build stopped at configure with its output thrown away. The script installs nasm there and prints the log tail."""
    sh = (ROOT / "setup" / "build_lgpl_av").read_text(encoding="utf-8")
    assert '[ "$(uname -m)" = x86_64 ] && ! command -v nasm' in sh
    assert "brew install nasm" in sh
    assert sh.index("brew install nasm") < sh.index("./configure")
    assert 'tail -n 40 "$work/src/ffbuild/config.log"' in sh
