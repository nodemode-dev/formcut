from conftest import ROOT


def test_the_windows_ffmpeg_build_falls_back_to_the_family_copy_of_the_source():
    script = (ROOT / "setup" / "build_lgpl_ffmpeg_msvc").read_text(encoding="utf-8")
    fetch = script[script.index('tarball="ffmpeg-$version.tar.xz"'):script.index("sha256sum")]
    assert "https://ffmpeg.org/releases/$tarball" in fetch
    assert "https://dl.formai.studio/sources/ffmpeg/$tarball" in fetch
    assert fetch.index("ffmpeg.org") < fetch.index("dl.formai.studio")
    assert 'rm -f "$tarball"' in fetch
