"""The Form functions (hub plan section 12): the manifest at the root matches the code, params are checked against it,
and each function runs headless on generated media, with no engine server. A test that needs a Whisper model skips
unless the model is already in the models folder (the tiny English one is 41 MB through the pinned fetcher)."""

from __future__ import annotations

import io
import json
import os
import shutil
import signal
import subprocess
import sys
import zipfile

import numpy as np
import pytest
from app import fast_export, media, project_files, project_packages, store
from app import transcribe as engine_transcribe
from app.assets import upload_lut
from app.functions import FunctionError, render_project, transcribe
from app.functions.__main__ import ROOT_MANIFEST, manifest_text
from app.functions.contract import checked_params
from app.render_document import validate_document
from conftest import ROOT
from fastapi import UploadFile

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None or FFPROBE is None, reason="ffmpeg makes the clips and ffprobe reads the result")
TINY = engine_transcribe.model_for("en", "tiny")


def _generated(path, source: str, seconds: float = 1.0, tone: int | None = 440, rate: int = 30):
    command = [FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"{source}=size=160x90:rate={rate}:duration={seconds}"]
    if tone:
        command += ["-f", "lavfi", "-i", f"sine=frequency={tone}:duration={seconds}", "-c:a", "aac", "-shortest"]
    subprocess.run([*command, "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


def _probe(path) -> dict:
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], capture_output=True, check=True
    )
    return json.loads(out.stdout)


def _stored_project(tmp_path, first_seconds: float = 1.0, first_rate: int = 30) -> str:
    """Two generated clips, one after the other, as the engine's own project model holds them, each in a 1 s slot."""
    first = media.ingest_path(_generated(tmp_path / "bars.mp4", "testsrc2", first_seconds, rate=first_rate), "bars.mp4")
    second = media.ingest_path(_generated(tmp_path / "rgb.mp4", "rgbtestsrc", tone=660), "rgb.mp4")
    clips = [
        {"id": "a", "kind": "video", "label": "bars", "mediaId": first["id"], "start": 0, "duration": 1, "sourceIn": 0},
        {"id": "b", "kind": "video", "label": "rgb", "mediaId": second["id"], "start": 1, "duration": 1, "sourceIn": 0},
    ]
    project = {
        "id": f"fn-{tmp_path.name}",
        "title": "Functions",
        "width": 160,
        "height": 90,
        "fps": 30,
        "duration": 2,
        "activeTimeline": 0,
        "timelines": [{"id": "t", "name": "t", "tracks": [{"id": "v", "name": "V", "clips": clips}]}],
    }
    return store.save_project(project)["id"]


@pytest.fixture
def package(tmp_path):
    built = project_packages.build(_stored_project(tmp_path))
    target = tmp_path / "Functions.fc"
    shutil.move(built, target)
    return target


def test_the_root_manifest_is_the_one_the_code_declares():
    from app.main import APP_VERSION

    written = json.loads(ROOT_MANIFEST.read_text(encoding="utf-8"))
    assert ROOT_MANIFEST == ROOT / "form-functions.json"
    assert ROOT_MANIFEST.read_text(encoding="utf-8") == manifest_text(), "run: cd backend && python -m app.functions manifest --write"
    assert written["app_version"] == APP_VERSION and written["format"] == "form-functions" and written["format_version"] == 1
    for function in written["functions"]:
        module, name = function["entry"].split(":")
        assert callable(getattr(__import__(module, fromlist=[name]), name)), function["entry"]
        assert set(function) == {"id", "title", "description", "entry", "inputs", "outputs", "params", "runs", "cost", "timeout_s"}


def test_params_take_their_defaults_and_refuse_what_the_schema_does_not_allow():
    assert checked_params("transcribe", {}) == {"model": "tiny", "language": "en"}
    assert checked_params("render_project", None) == {"format": "mp4", "quality": "high"}
    assert checked_params("transcribe", {"model": "large", "language": "auto"})["model"] == "large"
    with pytest.raises(FunctionError, match="expected one of tiny, base"):
        checked_params("transcribe", {"model": "huge"})
    with pytest.raises(FunctionError, match="unknown param 'codec'"):
        checked_params("render_project", {"codec": "h264"})
    with pytest.raises(FunctionError, match="language"):
        checked_params("transcribe", {"language": "English"})
    with pytest.raises(FunctionError, match="must be a string"):
        checked_params("render_project", {"quality": 3})


@pytest.mark.parametrize("function", [transcribe, render_project])
def test_a_missing_input_is_refused_before_anything_runs(function, tmp_path):
    with pytest.raises(FunctionError, match="is required"):
        function({}, {}, str(tmp_path / "out"))
    name = "media" if function is transcribe else "project"
    with pytest.raises(FunctionError, match="no file at"):
        function({name: str(tmp_path / "nothing.mp4")}, {}, str(tmp_path / "out"))


def test_a_file_that_is_not_a_project_is_refused(tmp_path):
    other = tmp_path / "notes.txt"
    other.write_text("hello", encoding="utf-8")
    with pytest.raises(FunctionError, match=r"give a \.fc package or a \.fmc file"):
        render_project({"project": str(other)}, {}, str(tmp_path / "out"))


@needs_ffmpeg
@pytest.mark.parametrize(("fmt", "codec"), [("mp4", "h264"), ("webm", "vp9")])
def test_a_package_renders_to_the_asked_format(package, tmp_path, fmt, codec):
    out = tmp_path / "out"
    try:
        result = render_project({"project": str(package)}, {"format": fmt, "quality": "low"}, str(out))
    except FunctionError as exc:
        if "no H.264 encoder" in str(exc):
            pytest.skip(str(exc))
        raise
    assert result == {"video": str((out / f"video.{fmt}").resolve())}
    probed = _probe(result["video"])
    video = next(s for s in probed["streams"] if s["codec_type"] == "video")
    assert (video["codec_name"], video["width"], video["height"]) == (codec, 160, 90)
    assert any(s["codec_type"] == "audio" for s in probed["streams"])
    assert float(probed["format"]["duration"]) == pytest.approx(2.0, abs=0.1)
    assert [p.name for p in out.iterdir()] == [f"video.{fmt}"]


@needs_ffmpeg
def test_a_clip_shorter_than_its_slot_is_held_and_the_render_finishes(tmp_path):
    """The native graph pads a 0.5 s, 24 fps clip in a 1 s slot by holding its last frame. On FFmpeg 7.1.5, the build
    formcut bundles, an unbounded tpad never finished and ignored SIGTERM; the render now ends within the limit. Set
    FORMCUT_FFMPEG_DIR to a formcut ffmpeg folder to run this against that build."""
    project_id = _stored_project(tmp_path, first_seconds=0.5, first_rate=24)
    assert fast_export.plan(validate_document(store.get_project(project_id)), 60) is not None  # the graph this is about
    built = tmp_path / "short.fc"
    shutil.move(project_packages.build(project_id), built)
    out = tmp_path / "out"
    command = [sys.executable, "-m", "app.functions", "run", "render_project", "--inputs", json.dumps({"project": str(built)})]
    command += ["--params", '{"format": "webm", "quality": "low"}', "--out", str(out)]
    # its own process group, so a hung ffmpeg (deaf to SIGTERM) is killed with everything else
    child = subprocess.Popen(command, cwd=ROOT / "backend", stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        _, error = child.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        os.killpg(child.pid, signal.SIGKILL)
        child.communicate()
        pytest.fail("the render did not finish within 90 s")
    assert child.returncode == 0, error.decode(errors="replace")
    probed = _probe(out / "video.webm")
    assert float(probed["format"]["duration"]) == pytest.approx(2.0, abs=0.1)

    def frame_at(seconds: float) -> np.ndarray:
        raw = subprocess.run(
            [
                FFMPEG,
                "-v",
                "error",
                "-ss",
                f"{seconds}",
                "-i",
                str(out / "video.webm"),
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "-",
            ],
            capture_output=True,
            check=True,
        ).stdout
        return np.frombuffer(raw, np.uint8).astype(np.int16)

    # the clip's last frame held through the rest of its slot, while testsrc2 itself moves from frame to frame
    assert np.abs(frame_at(0.6) - frame_at(0.95)).mean() < 2
    assert np.abs(frame_at(0.1) - frame_at(0.4)).mean() > 2


@needs_ffmpeg
def test_the_cli_runs_a_render_and_prints_one_json_line(package, tmp_path):
    out = tmp_path / "cli"
    inputs = json.dumps({"project": str(package)})
    run = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.functions",
            "run",
            "render_project",
            "--inputs",
            inputs,
            "--params",
            '{"format": "webm"}',
            "--out",
            str(out),
        ],
        cwd=ROOT / "backend",
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    lines = run.stdout.strip().splitlines()
    assert len(lines) == 1 and json.loads(lines[0]) == {"video": str((out / "video.webm").resolve())}
    bad = subprocess.run(
        [sys.executable, "-m", "app.functions", "run", "render_project", "--inputs", "{}", "--out", str(out)],
        cwd=ROOT / "backend",
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad.returncode == 1 and "input 'project' is required" in bad.stderr


IDENTITY_CUBE = "LUT_3D_SIZE 2\n" + "".join(f"{r} {g} {b}\n" for b in (0, 1) for g in (0, 1) for r in (0, 1))
ABSENT = "0123456789abcdef0123456789abcdef"


def _library_reference(kind: str, tmp_path) -> tuple[str, str]:
    """A library item that exists here (in the suite's own library) but is not in the package, and the field naming it."""
    if kind == "background":
        image = tmp_path / "backdrop.png"
        subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=160x90", "-frames:v", "1", str(image)], check=True)
        return "background", media.ingest_path(image, "backdrop.png")["id"]
    if kind == "lut":
        return "lutId", upload_lut(UploadFile(filename="look.cube", file=io.BytesIO(IDENTITY_CUBE.encode())))["id"]
    return ("shaderId" if kind == "shader" else "fontId"), ABSENT


def _repackaged(package, tmp_path, field: str, item_id: str):
    """The package with its project naming the library item: on the background, the first clip, or its text style."""
    changed = tmp_path / f"with-{field}.fc"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(changed, "w") as target:
        for name in source.namelist():
            raw = source.read(name)
            if name == "project.json":
                document = json.loads(raw)
                clip = document["timelines"][0]["tracks"][0]["clips"][0]
                if field == "background":
                    document["background"] = {"type": "image", "mediaId": item_id}
                elif field == "fontId":
                    text = {
                        "id": "t",
                        "kind": "text",
                        "label": "t",
                        "start": 0,
                        "duration": 1,
                        "textStyle": {"content": "x", "fontId": item_id},
                    }
                    document["timelines"][0]["tracks"].append({"id": "tt", "name": "T", "clips": [text]})
                else:
                    clip[field] = item_id
                raw = json.dumps(document).encode()
            target.writestr(name, raw)
    return changed


@needs_ffmpeg
@pytest.mark.parametrize("kind", ["background", "lut", "shader", "font"])
def test_a_library_item_the_package_does_not_carry_is_refused(package, tmp_path, kind):
    field, item_id = _library_reference(kind, tmp_path)
    crafted = _repackaged(package, tmp_path, field, item_id)
    named = {"background": "media", "lut": "LUT", "shader": "shader", "font": "font"}[kind]
    with pytest.raises(FunctionError, match=f"names a {named} \\({item_id}\\) that did not come with the project"):
        render_project({"project": str(crafted)}, {"format": "webm", "quality": "low"}, str(tmp_path / "out"))
    assert not (tmp_path / "out" / "video.webm").exists()


@needs_ffmpeg
def test_a_render_runs_in_its_own_data_folder_and_leaves_this_one_alone(package, tmp_path):
    import os

    before, environment = sorted(item["id"] for item in media.list_media()), dict(os.environ)
    render_project({"project": str(package)}, {"format": "webm", "quality": "low"}, str(tmp_path / "out"))
    assert sorted(item["id"] for item in media.list_media()) == before  # the package's media went to the child's library
    assert dict(os.environ) == environment


@needs_ffmpeg
def test_a_package_missing_its_media_is_refused(package, tmp_path):
    stripped = tmp_path / "stripped.fc"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(stripped, "w") as target:
        for name in source.namelist():
            if not name.startswith("media/") or name == "media/index.json":
                target.writestr(name, source.read(name))
    with pytest.raises(FunctionError, match="did not come with the project"):
        render_project({"project": str(stripped)}, {"format": "webm"}, str(tmp_path / "out"))


@needs_ffmpeg
@pytest.mark.skipif(sys.platform == "win32", reason="links need developer mode on Windows")
def test_a_collected_project_file_renders_from_the_media_beside_it(tmp_path):
    collected = project_files.collect(_stored_project(tmp_path), tmp_path / "Collected")
    result = render_project({"project": collected["path"]}, {"format": "webm", "quality": "low"}, str(tmp_path / "out"))
    assert float(_probe(result["video"])["format"]["duration"]) == pytest.approx(2.0, abs=0.1)


@needs_ffmpeg
def test_a_project_file_naming_media_outside_its_folder_is_refused(tmp_path):
    written = project_files.write_file(_stored_project(tmp_path), tmp_path / "Elsewhere" / "Loose.fmc")
    with pytest.raises(FunctionError, match="outside the project's folder"):
        render_project({"project": str(written)}, {"format": "webm"}, str(tmp_path / "out"))


@needs_ffmpeg
def test_media_without_audio_is_refused_with_a_reason(tmp_path):
    silent = _generated(tmp_path / "silent.mp4", "testsrc2", tone=None)
    with pytest.raises(FunctionError, match=r"no audio could be read from silent\.mp4"):
        transcribe({"media": str(silent)}, {}, str(tmp_path / "out"))


@needs_ffmpeg
@pytest.mark.skipif(not engine_transcribe.cached(TINY), reason=f"{TINY} is not downloaded here (models/hub)")
def test_transcribe_writes_a_transcript_and_captions(tmp_path):
    clip = _generated(tmp_path / "tone.mp4", "testsrc2", seconds=2.0)
    out = tmp_path / "out"
    result = transcribe({"media": str(clip)}, {"model": "tiny"}, str(out))
    assert result == {"transcript": str((out / "transcript.json").resolve()), "subtitles": str((out / "subtitles.srt").resolve())}
    transcript = json.loads((out / "transcript.json").read_text(encoding="utf-8"))
    assert transcript["model"] == TINY and transcript["duration"] == pytest.approx(2.0, abs=0.05)
    assert isinstance(transcript["segments"], list)
    for segment in transcript["segments"]:
        assert {"start", "end", "text", "words"} <= set(segment)
    assert (out / "subtitles.srt").is_file()
