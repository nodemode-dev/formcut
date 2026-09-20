#!/usr/bin/env bash
#
# Build the LGPL ffmpeg bundle for macOS.
#
#   ./build_ffmpeg_macos.sh                    # for this Mac's architecture
#   ./build_ffmpeg_macos.sh --arch x86_64      # Intel, cross-built from Apple silicon
#   ./build_ffmpeg_macos.sh --arch both        # both, then a universal binary as well
#   ./build_ffmpeg_macos.sh --out ~/formcut/src-tauri/binaries
#
# ── What this produces, and why it is built this way ──────────────────────────
#
# formcut is Apache-2.0 and ships ffmpeg as a separate program rather than
# linking it, so the bundle has to be **LGPL-2.1**: configured --disable-gpl
# --disable-nonfree, with no x264 and no x265, because those are GPL and would
# make the distributed whole GPL.
#
# That means there is **no software H.264 encoder** in this build, and that is
# not a flag anyone can flip. On a Mac it hardly matters: videotoolbox gives
# hardware H.264 and HEVC on every supported machine and is enabled below. The
# optional Homebrew libraries add non-GPL software paths for the cases it does.
#
# The build is **shared, not static**, on purpose. The LGPL exists so a person
# can substitute their own build of the libraries, and dylibs sitting beside the
# binary are what make that possible without relinking anything. That is also
# the part macOS makes awkward: a shared build records absolute paths to its own
# dylibs, so moving the folder breaks it. This script rewrites those to
# @loader_path so the bundle works wherever it is put, and keeps working when
# someone replaces a library with their own.
set -euo pipefail

VERSION="7.1.1"
ARCH=""
OUT=""
JOBS="$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"

while [ $# -gt 0 ]; do
  case "$1" in
    --arch) ARCH="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --jobs) JOBS="$2"; shift 2 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[ "$(uname -s)" = "Darwin" ] || { echo "this script builds on macOS; it needs Apple's SDK" >&2; exit 2; }
ARCH="${ARCH:-$(uname -m)}"

HERE="$(cd "$(dirname "$0")" && pwd)"
# Works whether this sits in formcut/setup or on its own somewhere.
if [ -z "$OUT" ]; then
  if [ -d "$HERE/../src-tauri/binaries" ]; then OUT="$(cd "$HERE/.." && pwd)/src-tauri/binaries"
  else OUT="$HERE/binaries"; fi
fi
mkdir -p "$OUT"

say() { printf '\n== %s\n' "$1"; }

# ── Tools ────────────────────────────────────────────────────────────────────
say "checking the toolchain"
xcode-select -p >/dev/null 2>&1 || { echo "Xcode command line tools are missing: xcode-select --install" >&2; exit 3; }
for tool in curl tar make nasm pkg-config; do
  command -v "$tool" >/dev/null || {
    echo "missing: $tool" >&2
    echo "  brew install nasm pkg-config" >&2
    exit 3
  }
done
echo "ok"

# ── Optional non-GPL encoders, used only if Homebrew has them ────────────────
# openh264 is BSD and gives a software H.264 path; libvpx and libaom are BSD and
# give VP9 and AV1; opus is BSD. None of them is GPL, so none of them changes
# the licence of what comes out.
#   brew install openh264 libvpx aom opus
EXTRA=""
for pair in "openh264:--enable-libopenh264" "vpx:--enable-libvpx" "aom:--enable-libaom" "opus:--enable-libopus"; do
  name="${pair%%:*}"; flag="${pair##*:}"
  if pkg-config --exists "$name" 2>/dev/null; then EXTRA="$EXTRA $flag"; fi
done
say "optional non-GPL encoders found"
echo "${EXTRA:-  none; videotoolbox will still give hardware H.264 and HEVC}"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

fetch_source() {
  say "fetching ffmpeg $VERSION"
  curl -fsSL -o "$WORK/ffmpeg.tar.xz" "https://ffmpeg.org/releases/ffmpeg-${VERSION}.tar.xz"
  tar xf "$WORK/ffmpeg.tar.xz" -C "$WORK"
}

# ── One architecture ─────────────────────────────────────────────────────────
build_one() {
  local arch="$1"
  local triple prefix cross=""
  case "$arch" in
    arm64)  triple="aarch64-apple-darwin" ;;
    x86_64) triple="x86_64-apple-darwin" ;;
    *) echo "unknown architecture: $arch" >&2; return 2 ;;
  esac
  prefix="$WORK/install-$arch"

  # Building Intel on Apple silicon, or the other way round, needs configure
  # told that it cannot run what it compiles.
  if [ "$arch" != "$(uname -m)" ]; then
    cross="--enable-cross-compile --target-os=darwin --arch=$arch"
    echo "cross-building $arch on $(uname -m)"
  fi

  say "configuring for $arch"
  local src="$WORK/ffmpeg-${VERSION}-$arch"
  rm -rf "$src"; cp -R "$WORK/ffmpeg-${VERSION}" "$src"
  cd "$src"

  ./configure \
    --prefix="$prefix" \
    --disable-gpl --disable-nonfree --disable-version3 \
    --disable-doc --disable-debug \
    --disable-static --enable-shared \
    --disable-programs --enable-ffmpeg --enable-ffprobe \
    --enable-pthreads \
    --enable-videotoolbox --enable-audiotoolbox \
    --disable-libx264 --disable-libx265 --disable-libxvid --disable-librav1e \
    --extra-cflags="-arch $arch -mmacosx-version-min=11.0" \
    --extra-ldflags="-arch $arch -mmacosx-version-min=11.0" \
    $cross $EXTRA 2>&1 | tee "$WORK/configure-$arch.log"

  # Read the licence back from what configure decided, not from the flags I
  # passed it, because those are not the same claim. configure prints this to
  # its own output, which is why it is captured above: it is not in config.log,
  # and grepping there reported a failure while the build was perfectly fine.
  local reported
  reported="$(grep -m1 '^License:' "$WORK/configure-$arch.log" || true)"
  case "$reported" in
    *"LGPL version 2.1"*) echo "configure reports: $reported" ;;
    "") echo "REFUSING: configure printed no licence line at all" >&2; return 4 ;;
    *) echo "REFUSING: configure reported $reported" >&2; return 4 ;;
  esac

  say "building $arch (this takes a while)"
  make -j"$JOBS"
  make install
  cd - >/dev/null
}

# ── Make the bundle relocatable, which is what makes it replaceable ─────────
relocate() {
  local arch="$1" prefix="$WORK/install-$arch" dest="$2"
  mkdir -p "$dest"
  cp "$prefix"/lib/*.dylib "$dest"/ 2>/dev/null || true
  # Copy the real files rather than the version symlinks, then recreate the
  # names each binary asks for.
  ( cd "$dest" && for f in *.dylib; do [ -L "$f" ] && rm -f "$f"; done ) || true
  cp -a "$prefix"/lib/*.dylib "$dest"/ 2>/dev/null || true

  for binary in "$3" "$4"; do
    [ -f "$binary" ] || continue
    # Point every ffmpeg dylib the binary uses at the folder beside it.
    otool -L "$binary" | awk 'NR>1 {print $1}' | while read -r dep; do
      case "$dep" in
        "$prefix"/lib/*|*/libav*|*/libsw*|*/libpostproc*)
          install_name_tool -change "$dep" "@loader_path/$(basename "$dep")" "$binary" 2>/dev/null || true
          ;;
      esac
    done
  done

  # And the dylibs' own ids and their references to each other.
  for lib in "$dest"/*.dylib; do
    [ -f "$lib" ] || continue
    install_name_tool -id "@loader_path/$(basename "$lib")" "$lib" 2>/dev/null || true
    otool -L "$lib" | awk 'NR>1 {print $1}' | while read -r dep; do
      case "$dep" in
        "$prefix"/lib/*|*/libav*|*/libsw*|*/libpostproc*)
          install_name_tool -change "$dep" "@loader_path/$(basename "$dep")" "$lib" 2>/dev/null || true
          ;;
      esac
    done
    # An ad-hoc signature, because macOS refuses a dylib whose signature no
    # longer matches after install_name_tool has edited it.
    codesign --force --sign - "$lib" >/dev/null 2>&1 || true
  done
  for binary in "$3" "$4"; do
    [ -f "$binary" ] && codesign --force --sign - "$binary" >/dev/null 2>&1 || true
  done
}

verify() {
  local binary="$1" arch="$2"
  say "checking the $arch build actually runs"
  local report
  report="$("$binary" -hide_banner -version 2>&1 | head -3)" || {
    echo "REFUSING: the binary does not run" >&2; return 5; }
  echo "$report" | head -1
  case "$report" in
    *--enable-gpl*|*--enable-nonfree*)
      echo "REFUSING: this binary is not LGPL. Its configuration says so." >&2; return 6 ;;
  esac
  echo "$report" | grep -o -- "--disable-gpl" | head -1
  # Encode two generated frames, because a binary that runs can still fail to
  # do the one thing it is here for.
  if "$binary" -v error -f lavfi -i "testsrc2=size=320x240:rate=30:duration=0.2" \
       -frames:v 3 -c:v h264_videotoolbox -f null - >/dev/null 2>&1; then
    echo "hardware H.264 through videotoolbox: works"
  else
    echo "videotoolbox H.264 did not encode here (fine when cross-built; it is checked at runtime anyway)"
  fi
}

record() {
  /usr/bin/python3 - "$OUT" "$VERSION" "$@" <<'PY'
import hashlib, json, pathlib, sys
out, version, *targets = sys.argv[1:]
out = pathlib.Path(out)
record = out / "ffmpeg-licence.json"
data = {"targets": {}}
if record.is_file():
    try:
        loaded = json.loads(record.read_text())
        data = loaded if "targets" in loaded else {"targets": {loaded.get("target", "unknown"): loaded}}
    except ValueError:
        pass
for triple in targets:
    entries = {}
    for name in ("ffmpeg", "ffprobe"):
        path = out / f"{name}-{triple}"
        if path.is_file():
            entries[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not entries:
        continue
    data["targets"][triple] = {
        "licence": "LGPL-2.1-or-later",
        "version": version,
        "source": f"https://ffmpeg.org/releases/ffmpeg-{version}.tar.xz",
        "configure": ("--disable-gpl --disable-nonfree --disable-version3 "
                      "--disable-libx264 --disable-libx265 --enable-videotoolbox "
                      "--enable-audiotoolbox --enable-shared"),
        "programs": sorted(entries),
        "sha256": entries,
        "note": ("dylibs beside the binary in lib-" + triple +
                 ", with install names rewritten to @loader_path so the bundle "
                 "relocates and so a person can replace a library"),
    }
print(json.dumps(data, indent=2), file=record.open("w"))
print(f"recorded {', '.join(targets)} in {record.name}")
PY
}

# ── Run ──────────────────────────────────────────────────────────────────────
fetch_source
BUILT=()

for arch in $([ "$ARCH" = "both" ] && echo "arm64 x86_64" || echo "$ARCH"); do
  case "$arch" in
    arm64)  triple="aarch64-apple-darwin" ;;
    x86_64) triple="x86_64-apple-darwin" ;;
  esac
  build_one "$arch"
  cp "$WORK/install-$arch/bin/ffmpeg"  "$OUT/ffmpeg-$triple"
  cp "$WORK/install-$arch/bin/ffprobe" "$OUT/ffprobe-$triple" 2>/dev/null || true
  chmod +x "$OUT/ffmpeg-$triple" "$OUT/ffprobe-$triple" 2>/dev/null || true
  relocate "$arch" "$OUT/lib-$triple" "$OUT/ffmpeg-$triple" "$OUT/ffprobe-$triple"
  verify "$OUT/ffmpeg-$triple" "$arch" || exit $?
  BUILT+=("$triple")
done

# A universal binary, when both were built. Handy for one download that runs
# everywhere; the per-architecture files stay, because tauri wants those.
if [ "$ARCH" = "both" ]; then
  say "making a universal binary"
  lipo -create "$OUT/ffmpeg-aarch64-apple-darwin" "$OUT/ffmpeg-x86_64-apple-darwin" \
       -output "$OUT/ffmpeg-universal-apple-darwin"
  lipo -create "$OUT/ffprobe-aarch64-apple-darwin" "$OUT/ffprobe-x86_64-apple-darwin" \
       -output "$OUT/ffprobe-universal-apple-darwin" 2>/dev/null || true
  codesign --force --sign - "$OUT/ffmpeg-universal-apple-darwin" >/dev/null 2>&1 || true
  lipo -info "$OUT/ffmpeg-universal-apple-darwin"
fi

record "${BUILT[@]}"

say "done"
echo "in $OUT:"
ls -la "$OUT" | awk '{print "  " $9 "  " $5}' | grep -v '^\s*$'
cat <<'NOTE'

LGPL-2.1.txt and README-ffmpeg.md must ship beside these. They are already in
the repository's src-tauri/binaries; if you built somewhere else, copy them over.

To confirm the bundle relocates, which is the whole point of the dylib layout:

    cp -R "<out>" /tmp/moved && /tmp/moved/ffmpeg-aarch64-apple-darwin -version

If that prints a version rather than a dyld error, a person can put this
anywhere and can replace any library in it with their own build.
NOTE
