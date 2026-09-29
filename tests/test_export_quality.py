"""Export quality and what the engine runs on (v2.2.8). The owner's exports through VideoToolbox came out at 2.4 Mbit/s
for 1080p and 3.3 for 1440p on High, a third of the sheet's estimate: its tier was "-q:v 45", a scale on which
VideoToolbox's higher numbers are the better ones. The export sheet was 360px wide with its labels, choices and footer
buttons wrapped into stacks. And nothing said whether the native engine ran."""

from __future__ import annotations

from pathlib import Path

from app import encoders, engine_report

ROOT = Path(__file__).resolve().parents[1]


def test_videotoolbox_gets_a_bitrate_that_rises_with_the_tier_and_the_picture():
    rate = lambda encoder, q, w, h: int(encoders.tier_flags(encoder, q, w, h, 30)[1].rstrip("k"))  # noqa: E731
    for encoder in ("h264_videotoolbox", "hevc_videotoolbox"):
        assert rate(encoder, "high", 1920, 1080) > rate(encoder, "medium", 1920, 1080) > rate(encoder, "low", 1920, 1080)
        assert rate(encoder, "high", 2560, 1440) > rate(encoder, "high", 1920, 1080)
    assert rate("h264_videotoolbox", "high", 1920, 1080) >= 9000  # was about 2400
    assert rate("h264_videotoolbox", "high", 2560, 1440) >= 15000  # was about 3300
    flags = encoders.tier_flags("h264_videotoolbox", "high", 1920, 1080, 30)
    assert "-maxrate" in flags and "-profile:v" in flags and "-q:v" not in flags
    assert encoders.tier_flags("some_unknown_hw", "high")[0] == "-b:v"  # no inverted quality scale anywhere
    assert encoders.tier_flags("libx264", "high") == ["-crf", "18"]  # software tiers unchanged


def test_the_estimate_is_the_rate_a_hardware_encoder_is_given():
    software = encoders.estimate_size("h264", 1920, 1080, 30, "high", 10, False)
    hardware = encoders.estimate_size("h264", 1920, 1080, 30, "high", 10, False, "h264_videotoolbox")
    given = encoders.hardware_kbps("h264_videotoolbox", "high", 1920, 1080, 30)
    assert abs(hardware["videoKbps"] - given) <= 1 and hardware["bytes"] > software["bytes"]


def test_the_engine_says_what_it_runs_on(capsys, monkeypatch):
    import sys

    state = engine_report.report()
    assert set(state) == {"native", "gpu", "ffmpeg"} and "zscale" in state["ffmpeg"] and "running" in state["native"]
    monkeypatch.setattr(sys, "__stderr__", sys.stderr)
    engine_report.say()
    said = capsys.readouterr().err
    assert "native engine:" in said and "ffmpeg:" in said and "GPU:" in said


def test_the_export_sheet_keeps_every_label_and_button_on_one_line():
    bar = (ROOT / "frontend" / "src" / "ui" / "titlebar.ts").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "src" / "styles" / "app.css").read_text(encoding="utf-8")
    assert 'class="modal-panel export-panel"' in bar and 'data-ref="hdr-note" hidden' in bar
    assert '${icon("pip")}Instagram</button>' in bar and 'title="${t("instagram.lastExport")}"' in bar
    assert ".modal-panel.export-panel { width: min(680px, 94vw)" in css and ".tool-chip, .btn-export { white-space: nowrap; }" in css
    assert ".export-panel .modal-row > .seg { flex-wrap: nowrap;" in css


def test_the_boot_checks_the_native_engine_and_builds_it_with_rust():
    boot = (ROOT / "setup" / "formcut_boot").read_text(encoding="utf-8")
    assert "import formcut_native" in boot and "setup/build_native_gpu" in boot and "FORMCUT_NATIVE_AUTOBUILD" in boot
