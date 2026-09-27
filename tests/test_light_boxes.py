"""MaxCLL and MaxFALL written into an MP4 as the clli and mdcv boxes, for the encoders that cannot take them as
SEI (VideoToolbox, NVENC, QSV, AMF); ffprobe reads them back and every packet is unchanged."""

import hashlib
import json
import shutil
import subprocess

import pytest
from app.render_api import write_light_boxes

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None, reason="needs ffmpeg and ffprobe")


def _make(path, faststart: bool) -> bool:
    command = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=160x96:r=25:d=0.4"]
    command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", *(["-movflags", "+faststart"] if faststart else []), str(path)]
    return subprocess.run(command, capture_output=True, check=False).returncode == 0


def _side(path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-select_streams", "v", "-of", "json", str(path)], capture_output=True, text=True
    ).stdout
    return {d.get("side_data_type"): d for d in json.loads(out)["streams"][0].get("side_data_list", [])}


def _packets(path) -> str:
    return hashlib.sha1(
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-map", "0", "-f", "framemd5", "-"], capture_output=True).stdout
    ).hexdigest()


@pytest.mark.parametrize("faststart", [True, False])
def test_the_light_is_read_back_and_the_picture_is_untouched(tmp_path, faststart):
    source = tmp_path / "plain.mp4"
    if not _make(source, faststart):
        pytest.skip("this ffmpeg has no libx264")
    boxed = tmp_path / "boxed.mp4"
    shutil.copy(source, boxed)
    assert write_light_boxes(boxed, 812, 203)
    side = _side(boxed)
    light = side["Content light level metadata"]
    assert (light["max_content"], light["max_average"]) == (812, 203)
    mastering = side["Mastering display metadata"]
    assert mastering["red_x"] == "34000/50000" and mastering["white_point_y"] == "16450/50000"
    assert mastering["max_luminance"] == "8120000/10000"
    assert _packets(source) == _packets(boxed)


def test_a_file_that_carries_the_boxes_is_left_alone(tmp_path):
    path = tmp_path / "once.mp4"
    if not _make(path, True):
        pytest.skip("this ffmpeg has no libx264")
    assert write_light_boxes(path, 1000, 400)
    before = path.read_bytes()
    assert not write_light_boxes(path, 1000, 400)
    assert path.read_bytes() == before
