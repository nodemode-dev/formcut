"""setup/bundle_ffmpeg.py: what it stages, what it clears, and what it refuses.

Offline: a small archive served from a file:// address stands in for the
formcut-binaries release, and the stage is a temporary folder.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import tarfile
from pathlib import Path

import pytest
from app import ffmpeg_fetch

ROOT = Path(__file__).resolve().parent.parent
TRIPLE = "aarch64-apple-darwin"
FILES = {f"ffmpeg-{TRIPLE}": b"ffmpeg", f"ffprobe-{TRIPLE}": b"ffprobe", f"lib-{TRIPLE}/libavutil.59.dylib": b"avutil"}


def _load():
    spec = importlib.util.spec_from_file_location("bundle_ffmpeg", ROOT / "setup" / "bundle_ffmpeg.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _archive(folder: Path, files: dict[str, bytes]) -> None:
    with tarfile.open(folder / f"ffmpeg-lgpl-7.1.5-2-{TRIPLE}.tar.gz", "w:gz") as bundle:
        for name, data in {**files, "LGPL-2.1.txt": b"licence"}.items():
            member = tarfile.TarInfo(f"ffmpeg-lgpl/{name}")
            member.size, member.mode = len(data), 0o755
            bundle.addfile(member, io.BytesIO(data))


@pytest.fixture
def staged(tmp_path, monkeypatch):
    module = _load()
    stage = tmp_path / "stage"
    stage.mkdir()
    for keep in ("README.md", ".gitignore"):
        (stage / keep).write_text(keep)
    (stage / "lib-x86_64-apple-darwin").mkdir()
    (stage / "ffmpeg").write_text("another target's")
    monkeypatch.setattr(module, "STAGE", stage)
    release = tmp_path / "release"
    release.mkdir()
    pins = [{"path": name, "sha256": hashlib.sha256(data).hexdigest()} for name, data in FILES.items()]
    monkeypatch.setattr(ffmpeg_fetch, "record", lambda: {"release": "7.1.5-2"})
    monkeypatch.setattr(ffmpeg_fetch, "pins", lambda record, triple: pins if triple == TRIPLE else [])
    monkeypatch.setenv("FORMCUT_FFMPEG_RELEASE", release.as_uri())
    monkeypatch.setattr("sys.argv", ["bundle_ffmpeg.py", "--target", TRIPLE])
    return module, stage, release


def _names(stage: Path) -> set[str]:
    return {path.relative_to(stage).as_posix() for path in stage.rglob("*") if path.is_file()}


def test_a_verified_build_is_staged_under_plain_names_and_nothing_else_is_left(staged):
    module, stage, release = staged
    _archive(release, FILES)
    assert module.main() == 0
    assert _names(stage) == {"README.md", ".gitignore", "ffmpeg", "ffprobe", f"lib-{TRIPLE}/libavutil.59.dylib", "LGPL-2.1.txt"}
    assert (stage / "ffmpeg").read_bytes() == b"ffmpeg"


def test_a_file_that_differs_fails_the_build_and_stages_nothing(staged):
    module, stage, release = staged
    _archive(release, {**FILES, f"ffmpeg-{TRIPLE}": b"not ffmpeg"})
    with pytest.raises(ValueError, match="does not match"):
        module.main()
    assert _names(stage) == {"README.md", ".gitignore"}


def test_the_old_release_address_is_tried_when_the_new_one_has_nothing(staged, monkeypatch, tmp_path, capsys):
    module, stage, _ = staged
    monkeypatch.delenv("FORMCUT_FFMPEG_RELEASE")
    old = tmp_path / "old" / "ffmpeg-7.1.5-2"
    old.mkdir(parents=True)
    _archive(old, FILES)
    monkeypatch.setattr(ffmpeg_fetch, "RELEASES", ((tmp_path / "new").as_uri(), (tmp_path / "old").as_uri()))
    assert module.main() == 0
    out = capsys.readouterr().out
    assert "new/ffmpeg-7.1.5-2" in out and "is not published" in out and f"from {old.as_uri()}/" in out
    assert (stage / "ffmpeg").read_bytes() == b"ffmpeg"


def test_the_old_release_address_is_tried_when_the_new_one_has_a_changed_build(staged, monkeypatch, tmp_path, capsys):
    module, stage, _ = staged
    monkeypatch.delenv("FORMCUT_FFMPEG_RELEASE")
    for where, files in (("new", {**FILES, f"ffmpeg-{TRIPLE}": b"not ffmpeg"}), ("old", FILES)):
        release = tmp_path / where / "ffmpeg-7.1.5-2"
        release.mkdir(parents=True)
        _archive(release, files)
    monkeypatch.setattr(ffmpeg_fetch, "RELEASES", ((tmp_path / "new").as_uri(), (tmp_path / "old").as_uri()))
    assert module.main() == 0
    out = capsys.readouterr().out
    assert "does not match the record" in out and f"from {(tmp_path / 'old').as_uri()}/" in out
    assert (stage / "ffmpeg").read_bytes() == b"ffmpeg"


def test_a_changed_build_at_every_address_fails_the_build_and_names_each(staged, monkeypatch, tmp_path):
    module, stage, _ = staged
    monkeypatch.delenv("FORMCUT_FFMPEG_RELEASE")
    for where in ("new", "old"):
        release = tmp_path / where / "ffmpeg-7.1.5-2"
        release.mkdir(parents=True)
        _archive(release, {**FILES, f"ffmpeg-{TRIPLE}": b"not ffmpeg"})
    monkeypatch.setattr(ffmpeg_fetch, "RELEASES", ((tmp_path / "new").as_uri(), (tmp_path / "old").as_uri()))
    with pytest.raises(ValueError, match="does not match") as raised:
        module.main()
    assert (tmp_path / "new").as_uri() in str(raised.value) and (tmp_path / "old").as_uri() in str(raised.value)
    assert _names(stage) == {"README.md", ".gitignore"}


def test_a_changed_build_at_one_address_and_nothing_at_the_other_still_fails_the_build(staged, monkeypatch, tmp_path):
    module, stage, _ = staged
    monkeypatch.delenv("FORMCUT_FFMPEG_RELEASE")
    release = tmp_path / "new" / "ffmpeg-7.1.5-2"
    release.mkdir(parents=True)
    _archive(release, {**FILES, f"ffmpeg-{TRIPLE}": b"not ffmpeg"})
    monkeypatch.setattr(ffmpeg_fetch, "RELEASES", ((tmp_path / "new").as_uri(), (tmp_path / "old").as_uri()))
    with pytest.raises(ValueError, match="does not match"):
        module.main()
    assert _names(stage) == {"README.md", ".gitignore"}


def test_no_release_address_with_the_build_stages_nothing(staged, monkeypatch, tmp_path, capsys):
    module, stage, _ = staged
    monkeypatch.delenv("FORMCUT_FFMPEG_RELEASE")
    monkeypatch.setattr(ffmpeg_fetch, "RELEASES", ((tmp_path / "new").as_uri(), (tmp_path / "old").as_uri()))
    assert module.main() == 0
    out = capsys.readouterr().out
    assert out.count("is not published") == 2 and "fetches ffmpeg on first run" in out
    assert _names(stage) == {"README.md", ".gitignore"}


def test_a_target_with_no_build_stages_nothing(staged, monkeypatch, capsys):
    module, stage, _ = staged
    monkeypatch.setattr("sys.argv", ["bundle_ffmpeg.py", "--target", "riscv64gc-unknown-linux-gnu"])
    assert module.main() == 0
    assert "fetches it on first run" in capsys.readouterr().out
    assert _names(stage) == {"README.md", ".gitignore"}
