"""H.264 through Cisco's OpenH264 on computers with no H.264 encoder.

The library is fetched from Cisco when an export first needs it, checked against
the recorded SHA-256, and used only while the person allows it; its licence is
shown with formcut's. The real tests fetch Cisco's genuine library once per run
and skip when Cisco's server cannot be reached.
"""

import math
import shutil
import subprocess

import numpy as np
import pytest
from app import openh264, render_api
from conftest import ROOT, make_project, text_clip

HAVE_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


@pytest.fixture
def codec_home(tmp_path, monkeypatch):
    monkeypatch.setattr(openh264, "DIR", tmp_path / "openh264")
    monkeypatch.setattr(openh264, "SETTINGS", tmp_path / "openh264.json")
    return tmp_path


@pytest.fixture(scope="session")
def cisco_library(tmp_path_factory):
    """Cisco's genuine library for this computer, fetched once for the whole run."""
    if openh264._binary() is None:
        pytest.skip("Cisco publishes no OpenH264 library for this computer")
    folder = tmp_path_factory.mktemp("cisco")
    saved = openh264.DIR
    openh264.DIR = folder
    try:
        return openh264.install()
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"Cisco's server could not be reached: {error}")
    finally:
        openh264.DIR = saved


def test_it_is_on_until_turned_off_and_off_means_unused(codec_home):
    assert openh264.enabled()
    openh264.set_enabled(False)
    assert not openh264.enabled() and openh264.library(download=True) is None
    openh264.set_enabled(True)
    assert openh264.status()["enabled"] and openh264.status()["notice"] == "OpenH264 Video Codec provided by Cisco Systems, Inc."


def test_a_download_that_is_not_the_recorded_library_is_not_kept(codec_home, monkeypatch):
    import bz2

    import httpx

    class Reply:
        content = bz2.compress(b"not cisco's library")

        def raise_for_status(self):
            return None

    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: Reply())
    if openh264._binary() is None:
        pytest.skip("no library for this computer")
    with pytest.raises(RuntimeError, match="did not match"):
        openh264.install()
    assert not any((codec_home / "openh264").glob("*")) if (codec_home / "openh264").exists() else True
    assert openh264.library(download=True) is None, "an export falls back instead"


def test_every_platform_formcut_ships_for_has_a_recorded_library():
    for key in (("linux", "x86_64"), ("darwin", "arm64"), ("win32", "x86_64")):
        name, digest = openh264.BINARIES[key]
        assert name.startswith(("libopenh264-2.6.0", "openh264-2.6.0")) and len(digest) == 64


def test_cisco_is_never_bundled_and_its_licence_is_carried():
    bundled = [p for p in ROOT.rglob("*openh264*") if p.suffix in (".so", ".dylib", ".dll", ".bz2") and ".git" not in p.parts]
    assert not bundled, "condition 1: downloaded to the person's computer, never bundled"
    for condition in ("separately downloaded", "ability to control", openh264.NOTICE, "reproduce all of the above text"):
        assert condition in openh264.LICENCE


def _psnr(a, b):
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    return math.inf if mse == 0 else 10 * math.log10(255**2 / mse)


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg makes the frames and the MP4")
def test_the_encoder_writes_every_frame_faithfully(cisco_library, tmp_path):
    width, height, rate, count = 320, 180, 30, 60
    source = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={width}x{height}:rate={rate}:duration={count / rate}",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "yuv420p",
            "-",
        ],
        capture_output=True,
        check=True,
    ).stdout
    intermediate = tmp_path / "in.mkv"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "yuv420p",
            "-s",
            f"{width}x{height}",
            "-r",
            str(rate),
            "-i",
            "-",
            "-c:v",
            "ffv1",
            str(intermediate),
        ],
        input=source,
        check=True,
    )
    output, log = tmp_path / "out.mp4", tmp_path / "log.txt"
    openh264.encode_mp4(cisco_library, intermediate, output, width, height, str(rate), 1_500_000, lambda _: None, lambda: False, log)
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_frames",
            "-show_entries",
            "stream=codec_name,nb_read_frames,avg_frame_rate",
            "-of",
            "csv=p=0",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert probe == f"h264,{rate}/1,{count}", probe
    back = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(output), "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"], capture_output=True, check=True
    ).stdout
    assert len(back) == len(source)
    assert _psnr(np.frombuffer(source, np.uint8), np.frombuffer(back, np.uint8)) >= 40


@pytest.mark.skipif(not HAVE_FFMPEG, reason="ffmpeg renders the export")
@pytest.mark.parametrize("route", [None, "layered", "frames"])
def test_an_h264_export_with_no_h264_encoder_goes_through_openh264(route, cisco_library, monkeypatch):
    from app.render_document import validate_document

    monkeypatch.setattr(render_api, "choose_encoder", {"vp9": "libvpx-vp9"}.get)
    monkeypatch.setattr(render_api.openh264, "library", lambda download=False: cisco_library)
    if route:
        monkeypatch.setenv("FORMCUT_EXPORT_PATH", route)
    project = validate_document(make_project(clips=[text_clip(duration=1.0)], duration=1.0))
    result = render_api.export_media(project, f"openh264-{route or 'default'}", lambda _: None, lambda: False, "mp4", "high")
    assert (
        result["codec"] == "h264" and result["encoder"] == "libopenh264" and result["file"].endswith(".mp4") and "fellBackTo" not in result
    )
    streams = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "csv=p=0", result["file"]],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    assert streams[0] == "h264" and "aac" in streams, streams
    assert not list((render_api.OUTPUTS).glob(f"openh264-{route or 'default'}.intermediate.*")), "the intermediate is removed"
