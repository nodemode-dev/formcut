import importlib.util
import os
import sys
from pathlib import Path

GPL_PARTS = ("x264", "x265", "postproc", "rubberband", "vidstab", "fdk-aac", "fdk_aac", "xvid", "frei0r")
CORE = ("avcodec", "avformat", "avutil", "avfilter", "avdevice", "swscale", "swresample")
LIB_SUFFIXES = (".so", ".dylib", ".dll", ".pyd")


def is_lib(path: Path) -> bool:
    name = path.name.lower()
    return any(name.endswith(s) or f"{s}." in name for s in LIB_SUFFIXES)


def main() -> int:
    spec = importlib.util.find_spec("av")
    if spec is None or not spec.origin:
        print("lgpl-av: PyAV is not installed, nothing to check")
        return 0
    package = Path(spec.origin).parent
    places = [package, package.parent / "av.libs", package / ".dylibs"]
    prefix = os.environ.get("LGPL_FFMPEG_PREFIX") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if prefix:
        places += [Path(prefix) / "lib", Path(prefix) / "bin"]
    libs = [p for d in places if d.is_dir() for p in d.rglob("*") if p.is_file() and is_lib(p)]
    gpl = sorted({p.name for p in libs if any(k in p.name.lower() for k in GPL_PARTS)})
    core = [p for p in libs if any(p.name.lower().startswith((c, "lib" + c)) for c in CORE)]
    wrong = []
    for path in core:
        data = path.read_bytes()
        marker = data.find(b" license: ")
        if marker < 0:
            continue
        text = data[marker + 10:marker + 40]
        if not text.startswith(b"LGPL"):
            wrong.append(f"{path.name} ({text.split(b'\0')[0].decode('ascii', 'replace')})")
    if gpl or wrong:
        print("lgpl-av: PyAV is linked to a GPL FFmpeg: " + ", ".join(gpl + wrong))
        print("lgpl-av: run setup/build_lgpl_av to rebuild PyAV against an LGPL FFmpeg")
        return 1
    if not core:
        print("lgpl-av: no FFmpeg libraries found beside PyAV; pass the FFmpeg prefix")
        return 1
    print(f"lgpl-av: PyAV uses LGPL FFmpeg ({len(core)} libraries checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
