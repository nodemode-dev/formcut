"""A clip whose media cannot be read (v2.2.6). The owner deleted media.json again and the preview failed with "Could not
decode source frame", the preview stream taking its connection down ("response already started"), with nothing to
say which file or why. Now the preview draws such a clip as a card naming it and the reason, and says so once in the
terminal; an export stops, naming the file; a device-path failure is read again on the CPU; and a media check reports
every item's file and whether it decodes."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest
from app import media, media_check, store
from app.renderer import FrameRenderer, MediaUnreadable

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg makes the clips")


def _clip(tmp_path, name):
    out = tmp_path / name
    subprocess.run(
        [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=30", "-t", "1", "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )
    return out


def _project(pairs, project_id):
    clips = [
        {"id": f"c{n}", "kind": "video", "label": label, "mediaId": media_id, "start": n, "duration": 1, "sourceIn": 0}
        for n, (media_id, label) in enumerate(pairs)
    ]
    return {
        "id": project_id,
        "title": project_id,
        "width": 160,
        "height": 90,
        "fps": 30,
        "duration": len(pairs),
        "activeTimeline": 0,
        "timelines": [{"id": "t", "name": "t", "tracks": [{"id": "v", "name": "V", "clips": clips}]}],
    }


def test_the_preview_draws_a_card_for_media_it_cannot_read_and_an_export_stops(tmp_path):
    good = media.ingest_path(_clip(tmp_path, "good.mp4"), "good.mp4")
    broken = media.ingest_path(_clip(tmp_path, "broken.mp4"), "broken.mp4")
    media.media_path(broken["id"]).write_bytes(b"not a video")
    project = _project([(good["id"], "good.mp4"), (broken["id"], "broken.mp4"), ("0" * 32, "gone.mp4")], "p-problems")
    preview = FrameRenderer(project, 160)
    fine, damaged, missing = preview.frame(0.5), preview.frame(1.5), preview.frame(2.5)
    assert fine.mean() > 30
    for card in (damaged, missing):
        assert card.shape == fine.shape and tuple(card[45, 2][:3]) != (0, 0, 0)  # a card with its red edge, not black
    with pytest.raises(MediaUnreadable, match=r"gone\.mp4: it is not in the media library"):
        FrameRenderer(project).frame(2.5)
    with pytest.raises(MediaUnreadable, match=r"broken\.mp4: the decoder could not open it"):
        FrameRenderer(project).frame(1.5)


def test_the_media_check_names_every_problem(tmp_path):
    good = media.ingest_path(_clip(tmp_path, "fine.mp4"), "fine.mp4")
    gone = media.ingest_path(_clip(tmp_path, "later-gone.mp4"), "later-gone.mp4")
    media.media_path(gone["id"]).unlink()
    store.save_project(_project([(good["id"], "fine.mp4"), ("1" * 32, "orphan.mp4")], "p-check"))
    report = media_check.check()
    by_id = {entry["id"]: entry for entry in report["items"]}
    assert by_id[good["id"]]["decodes"] is True and by_id[good["id"]]["device colour path"] == "reads"
    assert by_id[gone["id"]]["file"] == "missing" and gone["id"] in {entry["id"] for entry in report["problems"]}
    assert any(o["mediaId"] == "1" * 32 and o["clip"] == "orphan.mp4" for o in report["clipsWithoutMedia"])


def test_a_card_is_drawn_whatever_its_size():
    from app.renderer import placeholder

    for width, height in ((64, 36), (1080, 1920), (3840, 2160)):
        card = placeholder(width, height, MediaUnreadable("a very long file name for a clip.mp4", "its file is missing; relink it"))
        assert card.shape == (height, width, 4) and card.dtype == np.uint8
