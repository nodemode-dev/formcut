"""The HDR bench makes its PQ clip with the ffmpeg the desktop app ships.

`formcut-engine --bench --hdr` encoded its ten-bit PQ source with libx265, which
the LGPL build has no copy of, so the bench stopped before it began. Without
libx265 the clip is ProRes 422 HQ, still ten bits and still tagged PQ.
"""

import os

import pytest
from conftest import lgpl_ffmpeg


@pytest.mark.skipif(os.name == "nt", reason="the stand-in ffmpeg is a shell script")
def test_the_pq_clip_is_made_and_tagged_without_libx265(tmp_path, monkeypatch):
    from app import bench
    from app.media import media_path
    from app.video_source import _decoder_colours

    lgpl_ffmpeg(tmp_path, monkeypatch)
    project = bench._hdr_project(320, 180, 1.0)
    ids = [c["mediaId"] for tl in project["timelines"] for t in tl["tracks"] for c in t["clips"] if c.get("mediaId")]
    assert ids, project
    colours = _decoder_colours(media_path(ids[0]))
    assert colours.get("color_transfer") == "smpte2084" and colours.get("pix_fmt") == "yuv422p10le", colours
