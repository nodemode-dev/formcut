"""PyAV built from source on Windows finds FFmpeg's DLLs, at build time and in the frozen engine.

Python 3.8 and later ignore PATH when an extension module loads the DLLs it
depends on, so av/_core.pyd built against backend/.lgpl-ffmpeg could not load
avcodec-*.dll and the rest: PyInstaller logged "DLL load failed while importing
_core" and froze an engine without PyAV. The DLLs now sit beside PyAV, freeze.py
hands them to PyInstaller, and a PyAV that does not import stops the build.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from conftest import ROOT

sys.path.insert(0, str(ROOT / "setup"))
import vendor_av_dlls

CORE = ("avcodec-62.dll", "avformat-62.dll", "avutil-60.dll", "swscale-9.dll", "swresample-6.dll", "avfilter-11.dll", "avdevice-62.dll")


def _prefix(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "prefix" / "bin"
    bin_dir.mkdir(parents=True)
    for name in (*CORE, "README.txt"):
        (bin_dir / name).write_bytes(b"MZ" + name.encode())
    return tmp_path / "prefix"


def test_the_ffmpeg_dlls_are_the_dlls_in_the_prefix_bin(tmp_path):
    names = [p.name for p in vendor_av_dlls.ffmpeg_dlls(_prefix(tmp_path))]
    assert names == sorted(CORE)


def test_a_prefix_without_dlls_is_refused(tmp_path):
    (tmp_path / "prefix" / "bin").mkdir(parents=True)
    with pytest.raises(SystemExit):
        vendor_av_dlls.ffmpeg_dlls(tmp_path / "prefix")


def test_the_dlls_are_copied_beside_pyav(tmp_path):
    av_dir = tmp_path / "site-packages" / "av"
    av_dir.mkdir(parents=True)
    copied = vendor_av_dlls.copy_beside(_prefix(tmp_path), av_dir)
    assert sorted(p.name for p in copied) == sorted(CORE)
    assert all((av_dir / name).read_bytes() == b"MZ" + name.encode() for name in CORE)
    assert not (av_dir / "README.txt").exists()


def test_copying_twice_replaces_the_old_copies(tmp_path):
    prefix = _prefix(tmp_path)
    av_dir = tmp_path / "av"
    av_dir.mkdir()
    (av_dir / CORE[0]).write_bytes(b"stale")
    vendor_av_dlls.copy_beside(prefix, av_dir)
    assert (av_dir / CORE[0]).read_bytes() == b"MZ" + CORE[0].encode()


def test_the_import_check_reports_a_pyav_that_does_not_load(tmp_path):
    fake = tmp_path / "pkg" / "av"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text("raise ImportError('DLL load failed while importing _core')\n")
    ok, detail = vendor_av_dlls.imports_av(sys.executable, extra_path=tmp_path / "pkg")
    assert not ok
    assert "DLL load failed" in detail


def test_the_import_check_passes_a_pyav_that_loads(tmp_path):
    fake = tmp_path / "pkg" / "av"
    fake.mkdir(parents=True)
    (fake / "__init__.py").write_text("__version__ = '18.1.0'\n")
    ok, detail = vendor_av_dlls.imports_av(sys.executable, extra_path=tmp_path / "pkg")
    assert ok, detail
    assert "18.1.0" in detail


def test_the_windows_batch_puts_the_dlls_beside_pyav_after_building_it():
    lines = (ROOT / "setup" / "build_lgpl_av.bat").read_text(encoding="utf-8").splitlines()
    build = next(i for i, row in enumerate(lines) if "--no-binary av" in row)
    vendor = next(i for i, row in enumerate(lines) if "vendor_av_dlls.py" in row)
    check = next(i for i, row in enumerate(lines) if "check_lgpl_av.py" in row)
    assert build < vendor < check
    assert "|| exit /b 1" in lines[vendor]


def test_freeze_hands_the_ffmpeg_dlls_to_pyinstaller_on_windows():
    source = (ROOT / "backend" / "freeze.py").read_text(encoding="utf-8")
    assert "--add-binary" in source
    assert "ffmpeg_dlls(" in source
    assert "imports_av(" in source


def test_the_windows_release_refuses_an_engine_without_pyav():
    script = (ROOT / "setup" / "build_release").read_text(encoding="utf-8")
    assert '"pyav": "' in script


def test_the_script_runs_from_the_command_line(tmp_path):
    prefix = _prefix(tmp_path)
    av_dir = tmp_path / "av"
    av_dir.mkdir()
    (av_dir / "__init__.py").write_text("__version__ = '18.1.0'\n")
    run = subprocess.run(
        [sys.executable, str(ROOT / "setup" / "vendor_av_dlls.py"), str(prefix), "--av-dir", str(av_dir), "--skip-import"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    assert (av_dir / CORE[0]).is_file()
