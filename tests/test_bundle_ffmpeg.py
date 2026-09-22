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


def test_a_target_with_no_build_stages_nothing(staged, monkeypatch, capsys):
    module, stage, _ = staged
    monkeypatch.setattr("sys.argv", ["bundle_ffmpeg.py", "--target", "riscv64gc-unknown-linux-gnu"])
    assert module.main() == 0
    assert "fetches it on first run" in capsys.readouterr().out
    assert _names(stage) == {"README.md", ".gitignore"}
