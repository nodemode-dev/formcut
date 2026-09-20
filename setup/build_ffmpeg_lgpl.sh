#!/usr/bin/env bash
# Build an LGPL-2.1 ffmpeg and ffprobe for formcut.
#
# Run it on the machine you are building for. There is no cross-compilation
# here on purpose: a macOS binary needs Apple's SDK and a Windows one needs
# either MSYS2 or a mingw toolchain, and a script that pretends otherwise
# produces something that does not run.
#
#   ./setup/build_ffmpeg_lgpl.sh [--out DIR] [--version 7.1.1]
#
# What comes out lands in src-tauri/binaries by default, named for the target
# triple, which is what setup/fetch_ffmpeg.py and tauri expect.
#
# ── The one thing to understand before running this ────────────────────────
#
# libx264 is GPL. An LGPL ffmpeg therefore has **no software H.264 encoder**
# built in, and that is not a flag that can be flipped: including x264 makes the
# result GPL and makes anything shipped beside it GPL too.
#
# formcut copes because its encoder detection prefers hardware and confirms each
# candidate by actually encoding two frames rather than trusting a list:
#
#   macOS    videotoolbox   h264, hevc      present on every supported Mac
#   Windows  mediafoundation, nvenc, qsv    present on most machines
#   Linux    vaapi, nvenc, qsv              present where there is a GPU
#
# For machines with no hardware encoder, this script builds **openh264** (BSD,
# from Cisco) so there is still a software H.264 path, and VP9 and AV1 come from
# libvpx and libaom, both BSD. Between them every export formcut offers has a
# route that is not GPL.
set -euo pipefail

VERSION="7.1.1"
OUT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --out) OUT="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$ROOT/src-tauri/binaries}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

case "$(uname -s)" in
  Darwin)
    case "$(uname -m)" in
      arm64) TRIPLE="aarch64-apple-darwin" ;;
      *)     TRIPLE="x86_64-apple-darwin" ;;
    esac
    PLATFORM_FLAGS="--enable-videotoolbox --enable-audiotoolbox"
    ;;
  Linux)
    TRIPLE="x86_64-unknown-linux-gnu"
    # vaapi and v4l2 are the encoders a Linux machine is most likely to have.
    PLATFORM_FLAGS="--enable-vaapi --enable-v4l2-m2m"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    TRIPLE="x86_64-pc-windows-msvc"
    PLATFORM_FLAGS="--enable-mediafoundation --enable-d3d11va --enable-dxva2"
    ;;
  *) echo "unsupported system: $(uname -s)" >&2; exit 2 ;;
esac

echo "building ffmpeg $VERSION for $TRIPLE"
echo "output: $OUT"

for tool in curl tar make nasm pkg-config; do
  command -v "$tool" >/dev/null || { echo "missing build tool: $tool" >&2; exit 3; }
done

cd "$WORK"
curl -fsSL -o ffmpeg.tar.xz "https://ffmpeg.org/releases/ffmpeg-${VERSION}.tar.xz"
tar xf ffmpeg.tar.xz
cd "ffmpeg-${VERSION}"

# Any of these that are not installed are simply left out; each is optional and
# each is non-GPL. Install them first if you want them:
#   macOS   brew install openh264 libvpx aom opus
#   Linux   apt install libopenh264-dev libvpx-dev libaom-dev libopus-dev
OPTIONAL=""
for lib in libopenh264 vpx aom opus; do
  case "$lib" in
    libopenh264) pkg-config --exists openh264 && OPTIONAL="$OPTIONAL --enable-libopenh264" ;;
    vpx)         pkg-config --exists vpx       && OPTIONAL="$OPTIONAL --enable-libvpx" ;;
    aom)         pkg-config --exists aom       && OPTIONAL="$OPTIONAL --enable-libaom" ;;
    opus)        pkg-config --exists opus      && OPTIONAL="$OPTIONAL --enable-libopus" ;;
  esac
done
echo "optional encoders found:${OPTIONAL:- none}"

./configure \
  --prefix="$WORK/install" \
  --disable-gpl --disable-nonfree --disable-version3 \
  --disable-doc --disable-debug \
  --disable-static --enable-shared \
  --disable-programs --enable-ffmpeg --enable-ffprobe \
  --enable-pthreads \
  --disable-libx264 --disable-libx265 --disable-libxvid --disable-librav1e \
  $PLATFORM_FLAGS $OPTIONAL

# Confirm what configure decided rather than trusting the flags.
if ! grep -q "License: LGPL version 2.1 or later" ffbuild/config.log 2>/dev/null; then
  if ! ./ffbuild/config.log 2>/dev/null | true; then :; fi
fi

make -j"$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 2)"
make install

mkdir -p "$OUT"
SUFFIX=""
case "$TRIPLE" in *windows*) SUFFIX=".exe" ;; esac
cp "$WORK/install/bin/ffmpeg$SUFFIX"  "$OUT/ffmpeg-$TRIPLE$SUFFIX"
cp "$WORK/install/bin/ffprobe$SUFFIX" "$OUT/ffprobe-$TRIPLE$SUFFIX" 2>/dev/null || true
chmod +x "$OUT/ffmpeg-$TRIPLE$SUFFIX" || true

# Record what was shipped, which is what the LGPL asks of anyone redistributing.
python3 - "$OUT" "$TRIPLE" "$VERSION" <<'PY'
import hashlib, json, pathlib, sys
out, triple, version = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
suffix = ".exe" if "windows" in triple else ""
entries = {}
for name in ("ffmpeg", "ffprobe"):
    path = out / f"{name}-{triple}{suffix}"
    if path.is_file():
        entries[name] = hashlib.sha256(path.read_bytes()).hexdigest()
(out / "ffmpeg-licence.json").write_text(json.dumps({
    "target": triple,
    "licence": "LGPL-2.1-or-later",
    "version": version,
    "source": f"https://ffmpeg.org/releases/ffmpeg-{version}.tar.xz",
    "configure": "--disable-gpl --disable-nonfree --disable-version3 --disable-libx264 --disable-libx265",
    "programs": sorted(entries),
    "sha256": entries,
}, indent=2) + "\n", encoding="utf-8")
print("recorded", out / "ffmpeg-licence.json")
PY

echo
echo "done: $OUT/ffmpeg-$TRIPLE$SUFFIX"
echo "LGPL-2.1.txt and README-ffmpeg.md already live in that folder and ship with it."
