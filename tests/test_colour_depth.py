"""Ten- and twelve-bit sources keep their steps from the decoder to the last rounding.

A ten-bit 4:2:2 shadow ramp graded with a strong lift and a LUT used to reach the grade as bytes (swscale's bgr24)
and band; it now decodes to sixteen bits, grades and samples its LUT in float, and is dithered to bytes once. The
eight-bit path is checked to be the one it was: the same frame, to the bit, with the precise path switched off.
"""

from __future__ import annotations

import shutil
import uuid

import numpy as np
import pytest

av = pytest.importorskip("av", reason="the ten-bit source is written with PyAV")

WIDTH, HEIGHT = 1024, 16
LIFT = {"gain": {"y": 1.0}, "gamma": {"y": 0.6}}  # shadows lifted hard: twice the level, then a gamma lift


def _write(path, pix_fmt: str, codec: str, luma, frames: int = 3):
    """A clip whose luma is the given row (code values at the format's depth) on every line, neutral chroma."""
    fmt = av.VideoFormat(pix_fmt)
    bits = fmt.components[0].bits
    item = np.uint16 if bits > 8 else np.uint8
    with av.open(str(path), "w") as container:
        try:
            stream = container.add_stream(codec, rate=24)
        except (ValueError, av.FFmpegError) as exc:
            pytest.skip(f"this ffmpeg has no {codec} encoder ({exc})")
        stream.width, stream.height, stream.pix_fmt = WIDTH, HEIGHT, pix_fmt
        for _ in range(frames):
            frame = av.VideoFrame(WIDTH, HEIGHT, pix_fmt)
            for index, plane in enumerate(frame.planes[:3]):
                row = np.asarray(luma, np.float64) if index == 0 else np.full(WIDTH, 2 ** (bits - 1), np.float64)
                if plane.width != WIDTH:
                    row = row[:: WIDTH // plane.width]
                values = np.zeros((plane.height, plane.line_size // np.dtype(item).itemsize), item)
                values[:, : plane.width] = np.round(row[: plane.width]).astype(item)
                plane.update(values.tobytes())
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def _ingest(tmp_path, pix_fmt="yuv422p10le", codec="prores_ks", luma=None, suffix=".mov"):
    from app import media

    if luma is None:
        bits = av.VideoFormat(pix_fmt).components[0].bits
        scale = 2 ** (bits - 8)
        luma = np.linspace(24 * scale, 56 * scale, WIDTH)  # deep shadows, just above black
    path = _write(tmp_path / f"ramp-{uuid.uuid4().hex[:6]}{suffix}", pix_fmt, codec, luma)
    return media.ingest_path(path, path.name)["id"]


def _lut(name: str, size: int = 9) -> str:
    """A gentle S-curve 3D .cube in the asset folder, as an upload would leave it."""
    from app import assets

    steps = np.linspace(0, 1, size)
    curve = steps + 0.08 * np.sin(2 * np.pi * steps)
    rows = [f"{curve[r]:.6f} {curve[g]:.6f} {curve[b]:.6f}" for b in range(size) for g in range(size) for r in range(size)]
    asset_id = uuid.uuid4().hex
    assets.ROOT.mkdir(parents=True, exist_ok=True)
    (assets.ROOT / f"{asset_id}.cube").write_text(f'TITLE "{name}"\nLUT_3D_SIZE {size}\n' + "\n".join(rows) + "\n")
    (assets.ROOT / f"{asset_id}.json").write_text('{"kind": "lut"}')
    return asset_id


def _project(media_id: str, **clip):
    from conftest import make_project

    entry = {"id": "a", "kind": "video", "label": "ramp", "mediaId": media_id, "start": 0, "duration": 0.1, "sourceIn": 0.0, **clip}
    return make_project(width=WIDTH, height=HEIGHT, fps=24, duration=0.1, clips=[entry])


def _render(project, monkeypatch, path: str, precise: bool = True):
    from app.renderer import FrameRenderer

    for name in ("FORMCUT_COMPOSITE", "FORMCUT_EFFECTS"):
        monkeypatch.setenv(name, path)
    monkeypatch.setenv("FORMCUT_PRECISE", "1" if precise else "0")
    renderer = FrameRenderer(project)
    try:
        return renderer.frame(0.0)
    finally:
        renderer.close()


def _paths():
    from app import gpu

    found = ["cpu"]
    if gpu.status().get("available"):
        found.append("gpu")
    return found


def _steps(frame) -> tuple[int, int]:
    """(distinct output levels, largest gap between neighbouring levels) over the ramp's green channel."""
    levels = np.unique(frame[:, 8:-8, 1])
    return len(levels), int(np.diff(levels).max()) if len(levels) > 1 else 0


@pytest.mark.parametrize("path", _paths())
def test_a_ten_bit_422_shadow_ramp_graded_hard_with_a_lut_does_not_band(tmp_path, monkeypatch, path):
    media_id = _ingest(tmp_path)
    project = _project(media_id, colorGrade=LIFT, lutId=_lut("s-curve"))
    count, gap = _steps(_render(project, monkeypatch, path))
    coarse_count, coarse_gap = _steps(_render(project, monkeypatch, path, precise=False))
    # the lift spreads 32 byte levels of shadow over about a hundred output levels: through bytes they land
    # several levels apart; through sixteen bits and the dither every level between is used
    assert coarse_gap >= 3, (coarse_count, coarse_gap)
    assert gap <= 1, (count, gap)
    assert count >= 1.5 * coarse_count


@pytest.mark.parametrize("path", _paths())
def test_the_dithered_ramp_follows_the_unrounded_grade_on_average(tmp_path, monkeypatch, path):
    media_id = _ingest(tmp_path)
    frame = _render(_project(media_id, colorGrade=LIFT), monkeypatch, path).astype(np.float64)
    columns = frame[:, :, 1].mean(axis=0)
    # averaged over the 8 x 8 pattern the output rises steadily: no column step of more than a level
    smooth = np.convolve(columns, np.ones(8) / 8, mode="valid")
    assert np.abs(np.diff(smooth)).max() < 0.5


def test_a_ten_bit_source_decodes_to_sixteen_bits_and_an_eight_bit_one_stays_bytes(tmp_path):
    from app import media
    from app.video_source import acquire, recycle

    ten = media.MEDIA_DIR / next(p.name for p in media.MEDIA_DIR.glob(f"{_ingest(tmp_path)}.*"))
    eight_id = _ingest(tmp_path, "yuv420p", "mpeg4", np.linspace(16, 48, WIDTH), ".mp4")
    eight = next(media.MEDIA_DIR.glob(f"{eight_id}.*"))
    source = acquire(ten, None, 0, precise=True)
    ok, frame = source.read()
    recycle(source)
    assert ok and source.bits == 10 and frame.dtype == np.uint16 and frame.shape[2] == 4
    assert len(np.unique(frame[:, :, 1])) > 60  # 97 ten-bit codes; bytes would hold 33
    source = acquire(eight, None, 0, precise=True)
    ok, frame = source.read()
    recycle(source)
    assert ok and source.bits == 8 and frame.dtype == np.uint8


@pytest.mark.parametrize(("pix_fmt", "codec", "suffix"), [("yuv420p10le", "ffv1", ".mkv"), ("yuv444p12le", "ffv1", ".mkv")])
def test_ten_bit_420_and_twelve_bit_444_keep_their_steps_too(tmp_path, monkeypatch, pix_fmt, codec, suffix):
    media_id = _ingest(tmp_path, pix_fmt, codec, suffix=suffix)
    count, gap = _steps(_render(_project(media_id, colorGrade=LIFT), monkeypatch, "cpu"))
    assert gap <= 1, (pix_fmt, count, gap)


@pytest.mark.parametrize("path", _paths())
def test_the_eight_bit_fast_path_is_the_frame_it_was(tmp_path, monkeypatch, path):
    media_id = _ingest(tmp_path, "yuv420p", "mpeg4", np.linspace(16, 235, WIDTH), ".mp4")
    project = _project(media_id, colorGrade=LIFT, lutId=_lut("s-curve"), colour={"saturation": 20})
    now = _render(project, monkeypatch, path)
    before = _render(project, monkeypatch, path, precise=False)
    assert now.dtype == np.uint8 and np.array_equal(now, before)


def test_dithering_leaves_a_frame_of_bytes_as_it_was():
    from app.renderer import _to_bytes, dither_to_bytes

    rng = np.random.default_rng(3)
    exact = rng.integers(0, 256, (37, 53, 4)).astype(np.uint16) * 257
    assert np.array_equal(dither_to_bytes(exact), _to_bytes(exact))
    between = np.full((8, 8, 4), 257 * 100 + 128, np.uint16)  # half way from 100 to 101
    out = dither_to_bytes(between)[:, :, 0]
    assert set(np.unique(out)) == {100, 101} and abs(out.mean() - 100.5) < 0.02


@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")
def test_a_graded_deep_source_is_exported_by_the_frame_path_not_the_byte_graph(tmp_path, monkeypatch):
    from app.render_api import export_media
    from app.render_document import validate_document

    monkeypatch.delenv("FORMCUT_EXPORT_PATH", raising=False)
    deep = _ingest(tmp_path)
    eight = _ingest(tmp_path, "yuv420p", "mpeg4", np.linspace(16, 235, WIDTH), ".mp4")
    grade = {"colour": {"exposure": 0.2}}

    def path_of(media_id):
        project = validate_document(_project(media_id, **grade))
        return export_media(project, f"depth-{media_id[:6]}", lambda f: None, lambda: False, "webm", "high")["renderPath"]

    assert path_of(deep) == "frames"
    assert path_of(eight) == "layered"


@pytest.mark.parametrize("path", _paths())
def test_a_clip_marked_s_log3_shows_its_grey_where_rec709_puts_grey(tmp_path, monkeypatch, path):
    media_id = _ingest(tmp_path, luma=np.full(WIDTH, 420.0))  # 18% grey in S-Log3, ten-bit code 420
    as_shot = _render(_project(media_id), monkeypatch, path)[:, :, 1].mean()
    shown = _render(_project(media_id, inputColour="slog3"), monkeypatch, path)[:, :, 1].astype(np.float64)
    assert abs(as_shot - 255 * (420 - 64) / 876) < 1.5  # flat and bright, as Log looks before its transform
    assert abs(shown.mean() - 255 * (1.099 * 0.18**0.45 - 0.099)) < 1.5
