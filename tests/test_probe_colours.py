"""The probe without ffprobe (an LGPL bundle ships ffmpeg alone) reads a stream's pixel format and colour from
ffmpeg's report, as ffprobe names them. Without it every HDR source was taken for SDR: decoded to eight bits
with no tone-map and lifted into an HDR timeline as if it were sRGB."""

from app.tools import _video_colours

PQ = "  Stream #0:0[0x1](und): Video: hevc (Main 10) (hev1 / 0x31766568), yuv420p10le(tv, bt2020nc/bt2020/smpte2084, progressive), 1920x1080 [SAR 1:1 DAR 16:9], 30 fps"
HLG = "  Stream #0:0: Video: hevc (Main 10), yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67), 3840x2160, 25 fps"
SDR = "  Stream #0:0(und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(tv, bt709, progressive), 1920x1080 [SAR 1:1 DAR 16:9], 29.97 fps"
FULL = "  Stream #0:0: Video: h264 (High), yuvj420p(pc, progressive), 1280x720, 30 fps"
SWAPPED = "  Stream #0:0: Video: mpeg2video (Main), yuv420p(tv, smpte170m, top coded first (swapped)), 720x480, 29.97 fps"
PLAIN = "  Stream #0:0: Video: prores (HQ) (apch / 0x68637061), yuv422p10le, 1920x1080, 25 fps"


def test_a_pq_stream_is_named_as_ffprobe_names_it():
    assert _video_colours(PQ) == {
        "pix_fmt": "yuv420p10le",
        "color_range": "tv",
        "color_space": "bt2020nc",
        "color_primaries": "bt2020",
        "color_transfer": "smpte2084",
    }


def test_an_hlg_stream_carries_its_transfer():
    assert _video_colours(HLG)["color_transfer"] == "arib-std-b67"


def test_one_name_means_all_three():
    colours = _video_colours(SDR)
    assert colours["color_space"] == colours["color_primaries"] == colours["color_transfer"] == "bt709"


def test_full_range_and_nothing_else():
    assert _video_colours(FULL) == {"pix_fmt": "yuvj420p", "color_range": "pc"}


def test_a_field_order_with_parentheses_is_not_a_colour():
    assert _video_colours(SWAPPED)["color_transfer"] == "smpte170m"


def test_a_stream_with_no_colour_gives_its_pixel_format_only():
    assert _video_colours(PLAIN) == {"pix_fmt": "yuv422p10le"}
