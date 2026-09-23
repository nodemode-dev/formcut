"""Two failures the Windows and macOS check runners found.

A grade's .cube path went into the layered export's filter graph quoted once, and
ffmpeg split a Windows path at its drive colon: every graded clip on that path
failed to export on Windows. And a container whose frame count promised more
frames than it held made the renderer fail the whole export on the last one.
"""

import os
import shutil
import subprocess
from pathlib import Path, PureWindowsPath

import numpy as np
import pytest
from app import renderer
from app.fast_layers import filter_path


def test_a_windows_path_keeps_its_drive_colon_in_a_filter():
    assert filter_path(PureWindowsPath(r"C:\Users\runner\grade0.cube")) == r"'C\:/Users/runner/grade0.cube'"
    assert filter_path(Path("/srv/grades/grade0.cube")) == "'/srv/grades/grade0.cube'"


@pytest.mark.skipif(shutil.which("ffmpeg") is None or os.name == "nt", reason="needs ffmpeg, and a folder name with a colon")
def test_ffmpeg_reads_a_cube_from_a_path_with_a_colon(tmp_path):
    # A colon in a folder name breaks an unescaped path the way C: does on Windows.
    folder = tmp_path / "grade:dir"
    folder.mkdir()
    cube = folder / "grade0.cube"
    points = [f"{r} {g} {b}" for b in (0, 1) for g in (0, 1) for r in (0, 1)]
    cube.write_text("LUT_3D_SIZE 2\n" + "\n".join(points) + "\n", encoding="ascii")
    graph = f"lut3d=file={filter_path(cube)}:interp=trilinear"
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=16x16", "-vf", graph, "-frames:v", "1", "-f", "null", "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


class _ShortCapture:
    """Promises 30 frames, as a duration-derived count can, and holds 28."""

    fps, frame_count, held = 30.0, 30, 28

    def __init__(self):
        self.position = 0

    def seek(self, index):
        self.position = index

    def read(self):
        index, self.position = self.position, self.position + 1
        if index >= self.held:
            return False, None
        return True, np.full((18, 32, 3), index, np.uint8)


def test_past_the_last_real_frame_the_renderer_holds_it(tmp_path, monkeypatch):
    (tmp_path / "m1.mp4").write_bytes(b"")
    monkeypatch.setattr(renderer, "MEDIA_DIR", tmp_path)
    monkeypatch.setattr(renderer, "_find", lambda media_id: {"width": 32, "height": 18})
    monkeypatch.setattr(renderer.FrameRenderer, "_cursor", lambda self, media_id, time, path: "c")
    worker = renderer.FrameRenderer.__new__(renderer.FrameRenderer)
    worker.sources, worker.frames, worker.frame_numbers = {"c": _ShortCapture()}, {}, {}
    worker.stills, worker.decode_scale, worker.decode_limit, worker.allow_proxy = {}, {}, None, False
    clip = {"kind": "video", "mediaId": "m1"}
    last = worker.media_frame(clip, 27 / 30)
    assert int(last[0, 0, 0]) == 27
    after = worker.media_frame(clip, 29 / 30)
    assert int(after[0, 0, 0]) == 27, "the frame past the end should hold the last real one"
    jumped = renderer.FrameRenderer.__new__(renderer.FrameRenderer)
    jumped.sources, jumped.frames, jumped.frame_numbers = {"c": _ShortCapture()}, {}, {}
    jumped.stills, jumped.decode_scale, jumped.decode_limit, jumped.allow_proxy = {}, {}, None, False
    assert int(jumped.media_frame(clip, 29 / 30)[0, 0, 0]) == 27, "a seek straight past the end should step back to it"
