#!/usr/bin/env bash
#
# build_ffmpeg_lgpl_macos v1.1.0
#
# Builds FFmpeg from source in an LGPL-only configuration and packages ffmpeg,
# ffprobe and their shared libraries into a relocatable bundle that can ship
# inside a proprietary application and be moved, copied or replaced by the user.
#
# Modes
#   (default)      fetch, build, assemble, relocate, sign, clean-room verify, package
#   --repair       fix and repackage a bundle that already exists in --out, no compiling
#   --verify-only  run the clean-room contract against an existing tarball
#
# Written for stock macOS bash 3.2. Every conditional is written as if/fi rather
# than `[ c ] && action`, because the latter exits the script under `set -e`
# whenever the condition is false, and half the logic here is conditional.
#
# Source with FFLGPL_SOURCE_ONLY=1 to load the functions without running.

set -euo pipefail

VERSION="v1.1.0"

# ---------------------------------------------------------------------------
# Pinned sources. These checksums were computed from the downloaded tarballs.
# A version absent from the table is refused unless --ffmpeg-sha256 is given.
# ---------------------------------------------------------------------------

ffmpeg_sha256_for() {
  case "$1" in
    7.1.1) echo "733984395e0dbbe5c046abda2dc49a5544e7e0e1e2366bba849222ae9e3a03b1" ;;
    7.1.5) echo "de668509caf9e35e3cd162473441fdb29538c6d96ed080292b3cf9e6fc5d558f" ;;
    9.0.2) echo "8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e" ;;
    *)     echo "" ;;
  esac
}

OPUS_VERSION="1.6.1"
OPUS_SHA256="6ffcb593207be92584df15b32466ed64bbec99109f007c82205f0194572411a1"
OPUS_URL="https://downloads.xiph.org/releases/opus/opus-1.6.1.tar.gz"

VPX_VERSION="1.17.0"
VPX_SHA256="1020f184046187baa2985dbde38e0691f49c44088bca7a1842b0236c6081dc0a"
VPX_URL="https://github.com/webmproject/libvpx/archive/refs/tags/v1.17.0.tar.gz"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

MODE="build"
ARCH="$(uname -m 2>/dev/null || echo arm64)"
case "$ARCH" in
  arm64|aarch64) ARCH="arm64" ;;
  x86_64)        ARCH="x86_64" ;;
esac
HOST_ARCH="$ARCH"

FFMPEG_VERSION="7.1.5"
FFMPEG_SHA256_OVERRIDE=""
DEPLOYMENT_TARGET="11.0"
OUT_DIR="$PWD/binaries"
JOBS="$(sysctl -n hw.ncpu 2>/dev/null || echo 4)"
WITH_VPX=1
WITH_OPUS=1
LIB_SOURCE=""
LICENCE_FILE=""
TARBALL=""
KEEP_BUILD=0

say()  { printf '\n== %s\n' "$*"; }
step() { printf '   %s\n' "$*"; }
die()  { printf '\nREFUSING: %s\n' "$*" >&2; exit 1; }

usage() {
  cat <<'USAGE'
build_ffmpeg_lgpl_macos v1.1.0

  ./build_ffmpeg_lgpl_macos_v1.1.0.sh [options]
  ./build_ffmpeg_lgpl_macos_v1.1.0.sh --repair --out DIR [--lib-source PREFIX]
  ./build_ffmpeg_lgpl_macos_v1.1.0.sh --verify-only --tarball FILE.tar.gz

Options
  --arch arm64|x86_64|both   architecture to build        (default: this machine)
  --out DIR                  where the bundle is written  (default: ./binaries)
  --ffmpeg-version X.Y.Z     FFmpeg release               (default: 7.1.5)
  --ffmpeg-sha256 HEX        required for a version not in the pinned table
  --deployment-target X.Y    minimum macOS                (default: 11.0)
  --jobs N                   parallel make jobs           (default: ncpu)
  --no-libvpx                omit VP8/VP9 encoding
  --no-libopus               omit the libopus encoder
  --lib-source PREFIX        repair mode: where to look for missing dylibs
  --licence-file PATH        repair mode: COPYING.LGPLv2.1 to ship in the bundle
  --tarball FILE             verify-only mode: the bundle to check
  --keep-build               keep the build tree (verification is then skipped)
  -h, --help                 this text

Gates that abort the run
  configure must report "License: LGPL version 2.1 or later"
  CONFIG_GPL and CONFIG_NONFREE must both be 0 in config.h
  no dependency path may point outside the bundle or the system
  no shipped Mach-O may require a macOS newer than --deployment-target
  the packaged binary's -buildconf must not mention gpl, nonfree, x264, x265, fdk
  the bundle must start, encode and read back a clip with the build tree deleted
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --arch)              ARCH="${2:-}"; shift 2 ;;
    --out)               OUT_DIR="${2:-}"; shift 2 ;;
    --ffmpeg-version)    FFMPEG_VERSION="${2:-}"; shift 2 ;;
    --ffmpeg-sha256)     FFMPEG_SHA256_OVERRIDE="${2:-}"; shift 2 ;;
    --deployment-target) DEPLOYMENT_TARGET="${2:-}"; shift 2 ;;
    --jobs)              JOBS="${2:-}"; shift 2 ;;
    --no-libvpx)         WITH_VPX=0; shift ;;
    --no-libopus)        WITH_OPUS=0; shift ;;
    --lib-source)        LIB_SOURCE="${2:-}"; shift 2 ;;
    --licence-file)      LICENCE_FILE="${2:-}"; shift 2 ;;
    --license-file)      LICENCE_FILE="${2:-}"; shift 2 ;;
    --tarball)           TARBALL="${2:-}"; shift 2 ;;
    --repair)            MODE="repair"; shift ;;
    --verify-only)       MODE="verify"; shift ;;
    --keep-build)        KEEP_BUILD=1; shift ;;
    -h|--help)           usage; exit 0 ;;
    *)                   die "unknown option: $1" ;;
  esac
done

triple_for() {
  case "$1" in
    arm64)  echo "aarch64-apple-darwin" ;;
    x86_64) echo "x86_64-apple-darwin" ;;
    *)      die "unknown arch: $1" ;;
  esac
}

# Follows a symlink chain without depending on readlink -f or python.
resolve_link() {
  local p="$1" n=0 t d
  while [ -L "$p" ]; do
    n=$((n + 1))
    if [ "$n" -gt 32 ]; then return 1; fi
    t="$(readlink "$p")"
    case "$t" in
      /*) p="$t" ;;
      *)  d="$(dirname "$p")"; p="$d/$t" ;;
    esac
  done
  printf '%s' "$p"
}

# ver_le A B -> true when A <= B, comparing dot-separated integers.
ver_le() {
  awk -v a="$1" -v b="$2" '
    BEGIN {
      na = split(a, x, "."); nb = split(b, y, ".")
      n = (na > nb ? na : nb)
      for (i = 1; i <= n; i++) {
        xi = (i <= na ? x[i] + 0 : 0); yi = (i <= nb ? y[i] + 0 : 0)
        if (xi < yi) { exit 0 }
        if (xi > yi) { exit 1 }
      }
      exit 0
    }'
}

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

preflight() {
  say "preflight"
  if [ "$(uname -s)" != "Darwin" ]; then
    die "this script produces Mach-O binaries and must run on macOS"
  fi

  local missing="" t
  for t in clang make curl shasum tar file otool install_name_tool codesign lipo; do
    if ! command -v "$t" >/dev/null 2>&1; then missing="$missing $t"; fi
  done
  # nasm assembles the x86 SIMD paths. An arm64-only build uses NEON and does
  # not need it, so it is not demanded of an Apple Silicon machine building
  # only for itself.
  if [ "$ARCH" = "x86_64" ] || [ "$ARCH" = "both" ]; then
    if ! command -v nasm >/dev/null 2>&1; then missing="$missing nasm"; fi
  fi
  if [ -n "$missing" ]; then
    die "missing tools:$missing
    nasm, if listed, is a build-time assembler (brew install nasm). Nothing it
    produces is linked into the bundle; every library is built from source."
  fi

  case "$ARCH" in
    arm64|x86_64|both) ;;
    *) die "--arch must be arm64, x86_64 or both" ;;
  esac

  # The licence gate and the clean-room run both execute what was built, so a
  # cross-build is only checkable if this Mac can run the other architecture.
  # Finding that out now costs a second; finding it after the compile costs
  # twenty minutes.
  local targets="$ARCH" a
  if [ "$ARCH" = "both" ]; then targets="arm64 x86_64"; fi
  for a in $targets; do
    if [ "$a" = "$HOST_ARCH" ]; then continue; fi
    if [ "$HOST_ARCH" = "arm64" ] && [ "$a" = "x86_64" ]; then
      if ! arch -x86_64 /usr/bin/true >/dev/null 2>&1; then
        die "x86_64 is a cross-build on this Mac, and its licence gate and clean-room
    run have to execute the result, which needs Rosetta 2. Install it with:
      softwareupdate --install-rosetta --agree-to-license
    then run this again."
      fi
      step "x86_64 is a cross-build here; Rosetta 2 is present, so the gates can run it"
    else
      die "an Intel Mac cannot execute arm64 code, so the gates could not check an
    arm64 build. Build arm64 on Apple silicon."
    fi
  done

  # Homebrew is pushed to the back of PATH and removed from every library and
  # include search path. This is the defence against the failure where Homebrew
  # dylibs were linked in, dragged libX11 behind them, and stamped the bundle
  # with a minimum macOS newer than the machines it had to run on.
  local cleaned
  cleaned="$(printf '%s' "$PATH" | tr ':' '\n' | grep -v '^/opt/homebrew' | grep -v '^/usr/local' | paste -sd: - || true)"
  if [ -n "$cleaned" ]; then
    PATH="$cleaned:/opt/homebrew/bin:/usr/local/bin"
    export PATH
  fi
  unset DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH DYLD_FRAMEWORK_PATH
  unset LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH LD_LIBRARY_PATH
  export MACOSX_DEPLOYMENT_TARGET="$DEPLOYMENT_TARGET"
  # Without this, macOS tar turns each file's extended attributes into a "._"
  # AppleDouble sidecar, which lands 14 junk entries in the tarball.
  export COPYFILE_DISABLE=1

  step "host macOS $(sw_vers -productVersion 2>/dev/null || echo unknown), targeting ${DEPLOYMENT_TARGET}+"
  step "arch $ARCH, $JOBS jobs"
}

fetch() {
  local url="$1" dest="$2" want="$3" have
  if [ -f "$dest" ]; then
    have="$(shasum -a 256 "$dest" | cut -d' ' -f1)"
    if [ "$have" = "$want" ]; then
      step "cached $(basename "$dest")"
      return 0
    fi
    rm -f "$dest"
  fi
  step "fetching $(basename "$dest")"
  curl -fL --retry 3 --proto '=https' --tlsv1.2 -o "$dest" "$url"
  have="$(shasum -a 256 "$dest" | cut -d' ' -f1)"
  if [ "$have" != "$want" ]; then
    die "checksum mismatch for $(basename "$dest")
    expected $want
    got      $have"
  fi
  step "sha256 verified"
}

# ---------------------------------------------------------------------------
# Dependencies, built from source and linked statically.
#
# libopus and libvpx are BSD licensed, so absorbing them into the LGPL shared
# libraries carries no replaceability obligation and leaves no third-party dylib
# in the bundle at all. What stays shared is exactly what the LGPL requires to
# stay replaceable: FFmpeg's own libraries.
# ---------------------------------------------------------------------------

build_deps() {
  local arch="$1" deps="$2" src="$3"
  local cflags="-arch $arch -mmacosx-version-min=${DEPLOYMENT_TARGET} -fPIC -O2"
  local ldflags="-arch $arch -mmacosx-version-min=${DEPLOYMENT_TARGET}"
  local host_flag=""
  case "$arch" in
    arm64)  host_flag="--host=aarch64-apple-darwin" ;;
    x86_64) host_flag="--host=x86_64-apple-darwin" ;;
  esac

  if [ "$WITH_OPUS" = "1" ]; then
    say "libopus ${OPUS_VERSION} for $arch, static"
    rm -rf "$src/opus-${OPUS_VERSION}"
    tar xzf "$src/opus-${OPUS_VERSION}.tar.gz" -C "$src"
    (
      cd "$src/opus-${OPUS_VERSION}"
      CFLAGS="$cflags" LDFLAGS="$ldflags" \
        ./configure --prefix="$deps" --enable-static --disable-shared \
                    --disable-doc --disable-extra-programs "$host_flag" >/dev/null
      make -j"$JOBS" >/dev/null
      make install >/dev/null
    )
    step "installed to $deps"
  fi

  if [ "$WITH_VPX" = "1" ]; then
    say "libvpx ${VPX_VERSION} for $arch, static"
    rm -rf "$src/libvpx-${VPX_VERSION}" "$src/vpx-build-$arch"
    tar xzf "$src/libvpx-${VPX_VERSION}.tar.gz" -C "$src"
    local vpx_target
    case "$arch" in
      arm64)  vpx_target="arm64-darwin20-gcc" ;;
      x86_64) vpx_target="x86_64-darwin20-gcc" ;;
    esac
    mkdir -p "$src/vpx-build-$arch"
    (
      cd "$src/vpx-build-$arch"
      CFLAGS="$cflags" LDFLAGS="$ldflags" \
        "$src/libvpx-${VPX_VERSION}/configure" \
          --target="$vpx_target" --prefix="$deps" \
          --enable-vp8 --enable-vp9 --enable-vp9-highbitdepth \
          --enable-pic --enable-static --disable-shared \
          --disable-examples --disable-tools --disable-docs \
          --disable-unit-tests >/dev/null
      make -j"$JOBS" >/dev/null
      make install >/dev/null
    )
    step "installed to $deps"
  fi
}

# ---------------------------------------------------------------------------
# FFmpeg
# ---------------------------------------------------------------------------

# One flag per line. Flags contain spaces, so callers read these into
# positional parameters rather than word-splitting them.
configure_flags() {
  local prefix="$1" deps="$2" arch="$3"
  printf '%s\n' \
    "--prefix=$prefix" \
    "--enable-shared" \
    "--disable-static" \
    "--disable-gpl" \
    "--disable-nonfree" \
    "--disable-version3" \
    "--install-name-dir=@rpath" \
    "--enable-pic" \
    "--disable-debug" \
    "--disable-doc" \
    "--disable-ffplay" \
    "--disable-sdl2" \
    "--disable-xlib" \
    "--disable-libxcb" \
    "--disable-libxcb-shm" \
    "--disable-libxcb-xfixes" \
    "--disable-libxcb-shape" \
    "--enable-videotoolbox" \
    "--enable-audiotoolbox" \
    "--arch=$arch" \
    "--extra-cflags=-arch $arch -mmacosx-version-min=${DEPLOYMENT_TARGET} -I${deps}/include" \
    "--extra-ldflags=-arch $arch -mmacosx-version-min=${DEPLOYMENT_TARGET} -L${deps}/lib -headerpad_max_install_names"
  if [ "$WITH_VPX" = "1" ]; then printf '%s\n' "--enable-libvpx"; fi
  if [ "$WITH_OPUS" = "1" ]; then printf '%s\n' "--enable-libopus"; fi
  # Building for the other architecture is a cross-build. Without this flag,
  # configure links test programs for the target and then tries to run them.
  if [ "$arch" != "$HOST_ARCH" ]; then printf '%s\n' "--enable-cross-compile"; fi
}

build_ffmpeg() {
  local arch="$1" prefix="$2" deps="$3" src="$4" work="$5"
  local tree="$src/ffmpeg-${FFMPEG_VERSION}"
  local cfglog="$work/configure-$arch.log"

  rm -rf "$tree"
  tar xf "$src/ffmpeg-${FFMPEG_VERSION}.tar.xz" -C "$src"

  # PKG_CONFIG_LIBDIR replaces the default search path outright, so pkg-config
  # cannot see Homebrew even when it is installed.
  export PKG_CONFIG_LIBDIR="$deps/lib/pkgconfig"

  say "configuring FFmpeg ${FFMPEG_VERSION} for $arch"
  rm -rf "$work/ff-$arch"
  mkdir -p "$work/ff-$arch"
  if ! (
    cd "$work/ff-$arch"
    set --
    while IFS= read -r flag; do
      set -- "$@" "$flag"
    done <<FLAGS
$(configure_flags "$prefix" "$deps" "$arch")
FLAGS
    "$tree/configure" "$@" >"$cfglog" 2>&1
  ); then
    tail -40 "$cfglog" >&2
    die "configure failed for $arch, full log at $cfglog"
  fi

  licence_gate "$cfglog" "$work/ff-$arch"

  say "compiling $arch, this takes a while"
  (
    cd "$work/ff-$arch"
    make -j"$JOBS" >/dev/null
    make install >/dev/null
  )
  step "installed to $prefix"
}

licence_gate() {
  local cfglog="$1" builddir="$2" reported cfgh="" candidate

  reported="$(grep -m1 '^License:' "$cfglog" || echo "")"
  case "$reported" in
    *"LGPL version 2.1"*) step "configure reports: $reported" ;;
    "") die "configure printed no License line. That line goes to stdout rather than config.log, so its absence means the capture is wrong or the build is not what it claims." ;;
    *)  die "configure reported: $reported" ;;
  esac

  for candidate in "$builddir/ffbuild/config.h" "$builddir/config.h"; do
    if [ -f "$candidate" ]; then cfgh="$candidate"; break; fi
  done
  if [ -z "$cfgh" ]; then die "no config.h produced, the licence macros cannot be checked"; fi

  if ! grep -q '^#define CONFIG_GPL 0$' "$cfgh"; then
    die "CONFIG_GPL is not 0 in $cfgh"
  fi
  if ! grep -q '^#define CONFIG_NONFREE 0$' "$cfgh"; then
    die "CONFIG_NONFREE is not 0 in $cfgh"
  fi
  step "CONFIG_GPL 0 and CONFIG_NONFREE 0 confirmed in $(basename "$cfgh")"
}

# ---------------------------------------------------------------------------
# Assembly
#
# Every dependency is resolved to a regular file. The bundle contains no
# symbolic links, which is what defeated the previous attempt: a link was
# copied, its target was not, and a dangling link still satisfies `test -e`.
# ---------------------------------------------------------------------------

is_system_dep() {
  case "$1" in
    /usr/lib/*|/System/Library/*) return 0 ;;
    *) return 1 ;;
  esac
}

is_relative_dep() {
  case "$1" in
    @rpath/*|@loader_path/*|@executable_path/*) return 0 ;;
    *) return 1 ;;
  esac
}

deps_of() {
  otool -L "$1" | awk 'NR > 1 { print $1 }'
}

mach_o_files_in() {
  find "$1" -type f -print | while IFS= read -r f; do
    if file -b "$f" 2>/dev/null | grep -q 'Mach-O'; then
      printf '%s\n' "$f"
    fi
  done
}

copy_resolved() {
  local srcpath="$1" destdir="$2" base="$3" real a b
  if ! real="$(resolve_link "$srcpath")"; then
    die "symlink loop resolving $srcpath"
  fi
  if [ ! -f "$real" ]; then
    die "$srcpath resolves to '$real', which is not a regular file.
    This is the dangling-link case: the library was never installed where the
    link claims it is. Nothing is copied and nothing is guessed."
  fi
  mkdir -p "$destdir"
  cp -f "$real" "$destdir/$base"
  chmod u+w "$destdir/$base"
  if [ ! -f "$destdir/$base" ]; then
    die "copying $base into $destdir produced no regular file"
  fi
  a="$(shasum -a 256 "$real" | cut -d' ' -f1)"
  b="$(shasum -a 256 "$destdir/$base" | cut -d' ' -f1)"
  if [ "$a" != "$b" ]; then
    die "the copy of $base does not match its source by sha256"
  fi
}

# Fixed-point closure over the whole bundle. Terminating, and unable to skip a
# dependency the way a single pass did.
close_dependencies() {
  local bundle="$1" libdir="$2" search="$3"
  local round=0 changed f dep base found d

  while :; do
    round=$((round + 1))
    if [ "$round" -gt 24 ]; then
      die "the dependency closure did not settle after 24 rounds"
    fi
    changed=0
    while IFS= read -r f; do
      while IFS= read -r dep; do
        if is_system_dep "$dep"; then continue; fi
        base="$(basename "$dep")"
        if [ -f "$libdir/$base" ]; then continue; fi
        found=""
        while IFS= read -r d; do
          if [ -z "$d" ]; then continue; fi
          if [ -e "$d/$base" ]; then found="$d/$base"; break; fi
          if [ -L "$d/$base" ]; then
            die "$d/$base is a symbolic link whose target does not exist.
    It points at $(readlink "$d/$base"), which was never installed. A dangling
    link satisfies nothing, and copying one is how the last bundle shipped a
    library directory that held no libraries."
          fi
        done < <(printf '%s\n' "$search")
        if [ -z "$found" ] && ! is_relative_dep "$dep" && [ -e "$dep" ]; then
          found="$dep"
        fi
        if [ -z "$found" ]; then
          die "$(basename "$f") needs $base, and it is not in the bundle, not in
    the search path, and not at the path recorded in the binary.
      recorded as: $dep
      searched:
$(printf '%s\n' "$search" | sed 's/^/        /')
    A path that does not exist is what a deleted build tree looks like. Point
    --lib-source at a prefix that still has it, or rebuild."
        fi
        copy_resolved "$found" "$libdir" "$base"
        step "pulled in $base"
        changed=1
      done < <(deps_of "$f")
    done < <(mach_o_files_in "$bundle")
    if [ "$changed" -eq 0 ]; then break; fi
  done
  step "closure settled after $round round(s), $(find "$libdir" -type f | wc -l | tr -d ' ') libraries"
}

assemble() {
  local prefix="$1" bundle="$2" triple="$3" extra="${4:-}"
  local libdir="$bundle/lib-$triple" search links prog

  say "assembling the bundle for $triple"
  mkdir -p "$bundle" "$libdir"

  for prog in ffmpeg ffprobe; do
    if [ ! -f "$prefix/bin/$prog" ]; then
      die "$prefix/bin/$prog does not exist; the install step did not produce it"
    fi
    cp -f "$prefix/bin/$prog" "$bundle/$prog-$triple"
    chmod u+wx "$bundle/$prog-$triple"
    step "$prog-$triple"
  done

  search="$prefix/lib"
  if [ -n "$extra" ]; then
    search="$search
$extra
$extra/lib"
  fi
  close_dependencies "$bundle" "$libdir" "$search"

  links="$(find "$bundle" -type l | wc -l | tr -d ' ')"
  if [ "$links" != "0" ]; then
    die "$links symbolic link(s) in the bundle. Regular files only."
  fi
}

relocate() {
  local bundle="$1" triple="$2"
  local libdir="$bundle/lib-$triple" f base dep want

  say "rewriting install names"

  while IFS= read -r f; do
    base="$(basename "$f")"
    install_name_tool -id "@rpath/$base" "$f"
  done < <(find "$libdir" -type f -print)

  while IFS= read -r f; do
    while IFS= read -r dep; do
      if is_system_dep "$dep"; then continue; fi
      base="$(basename "$dep")"
      if [ "$dep" = "@rpath/$base" ]; then continue; fi
      install_name_tool -change "$dep" "@rpath/$base" "$f"
    done < <(deps_of "$f")
  done < <(mach_o_files_in "$bundle")

  # An LC_RPATH on each file so @rpath resolves. Executables look beside
  # themselves, libraries look in their own directory.
  while IFS= read -r f; do
    case "$f" in
      "$libdir"/*) want="@loader_path" ;;
      *)           want="@executable_path/lib-$triple" ;;
    esac
    if otool -l "$f" | grep -A2 LC_RPATH | grep -Fq "path $want "; then
      continue
    fi
    install_name_tool -add_rpath "$want" "$f"
  done < <(mach_o_files_in "$bundle")
  step "install names and rpaths rewritten"
}

resign() {
  local bundle="$1" triple="$2" f out

  say "re-signing"
  # install_name_tool invalidates the code signature. On Apple Silicon an
  # invalidly signed binary is killed on launch, so this is a correctness step
  # and never a formality. Libraries first, executables last.
  while IFS= read -r f; do
    if ! out="$(codesign --force --sign - --timestamp=none "$f" 2>&1)"; then
      die "codesign failed on $(basename "$f"):
$out"
    fi
    codesign --verify "$f"
  done < <(find "$bundle/lib-$triple" -type f -print; printf '%s\n' "$bundle/ffmpeg-$triple" "$bundle/ffprobe-$triple")
  step "every Mach-O signed ad-hoc and verified"
}

# ---------------------------------------------------------------------------
# Gates on the finished bundle, before anything is packaged
# ---------------------------------------------------------------------------

gate_paths() {
  local bundle="$1" f dep bad=0

  say "gate: no dependency points outside the bundle"
  while IFS= read -r f; do
    while IFS= read -r dep; do
      if is_system_dep "$dep"; then continue; fi
      if is_relative_dep "$dep"; then continue; fi
      printf '   LEAK %s -> %s\n' "$(basename "$f")" "$dep" >&2
      bad=$((bad + 1))
    done < <(deps_of "$f")
  done < <(mach_o_files_in "$bundle")
  if [ "$bad" -ne 0 ]; then
    die "$bad dependency path(s) still point outside the bundle. This is the
    exact defect that shipped last time."
  fi
  step "clean"
}

gate_minos() {
  local bundle="$1" want="$2" f got bad=0

  say "gate: nothing requires a macOS newer than $want"
  while IFS= read -r f; do
    got="$(otool -l "$f" | awk '/LC_BUILD_VERSION/ { b = 1 } b && /^ *minos/ { print $2; b = 0 }' | head -1)"
    if [ -z "$got" ]; then
      got="$(otool -l "$f" | awk '/LC_VERSION_MIN_MACOSX/ { b = 1 } b && /^ *version/ { print $2; b = 0 }' | head -1)"
    fi
    if [ -z "$got" ]; then continue; fi
    if ! ver_le "$got" "$want"; then
      printf '   HIGH %s requires macOS %s\n' "$(basename "$f")" "$got" >&2
      bad=$((bad + 1))
    fi
  done < <(mach_o_files_in "$bundle")
  if [ "$bad" -ne 0 ]; then
    die "$bad file(s) require a newer macOS than $want"
  fi
  step "clean"
}

gate_licence_binary() {
  local bundle="$1" triple="$2" conf lic

  say "gate: the packaged binary is LGPL"
  conf="$("$bundle/ffmpeg-$triple" -hide_banner -buildconf 2>&1)"
  if printf '%s' "$conf" | grep -qE 'enable-gpl|enable-nonfree|libx264|libx265|libfdk'; then
    printf '%s\n' "$conf" >&2
    die "the packaged binary reports a GPL or nonfree component"
  fi
  lic="$("$bundle/ffmpeg-$triple" -hide_banner -L 2>&1 | head -20 | tr '\n' ' ')"
  if ! printf '%s' "$lic" | grep -qi 'Lesser General Public'; then
    die "the binary's own -L output does not report the Lesser GPL:
$lic"
  fi
  printf '%s\n' "$conf" > "$bundle/BUILDCONF.txt"
  step "clean, buildconf recorded"
}

# ---------------------------------------------------------------------------
# Licence documents and manifest
# ---------------------------------------------------------------------------

write_documents() {
  local bundle="$1" triple="$2" licence="$3" notices_src="${4:-}"

  if [ -f "$licence" ]; then
    cp -f "$licence" "$bundle/COPYING.LGPLv2.1"
    step "COPYING.LGPLv2.1 taken from $licence"
  elif [ -f "$bundle/COPYING.LGPLv2.1" ]; then
    step "COPYING.LGPLv2.1 already in the bundle"
  else
    die "COPYING.LGPLv2.1 is neither at
      $licence
    nor already in the bundle. It must ship with the binaries, so this is a
    hard stop. Pass --licence-file pointing at the COPYING.LGPLv2.1 from the
    FFmpeg source this was built from."
  fi

  cat > "$bundle/README-replacing-ffmpeg.md" <<DOC
# Replacing the FFmpeg libraries

This bundle contains binaries from the FFmpeg project, used under the LGPL
v2.1. FFmpeg is a separate program here: it runs as its own process and nothing
links against it from inside the application.

The libraries are shared objects in \`lib-${triple}/\` beside the executables,
and that is deliberate. The LGPL exists so you can substitute your own build of
the libraries, and this layout lets you do that without relinking or rebuilding
anything.

## Replacing one library

Drop your own build in over the file of the same name in \`lib-${triple}/\`. It
has to keep the same install name, which you can read and set with:

    otool -D lib-${triple}/libavcodec.61.dylib
    install_name_tool -id @rpath/libavcodec.61.dylib your-libavcodec.61.dylib
    codesign --force --sign - your-libavcodec.61.dylib

The re-sign is required on Apple Silicon: editing a Mach-O invalidates its
signature, and an invalidly signed library will not load.

## Replacing the whole thing

Replace \`ffmpeg-${triple}\` and \`ffprobe-${triple}\` with any build of the
same major version. Inside a packaged application these live under
\`Contents/Resources/\`, reachable through Show Package Contents.

## What was built

FFmpeg ${FFMPEG_VERSION}, configured with --disable-gpl --disable-nonfree
--disable-version3. The full configure line is in \`MANIFEST.json\` and the
binary's own record of it is in \`BUILDCONF.txt\`. The corresponding source is
the official release tarball whose SHA-256 the manifest records, and it must be
hosted alongside any download of this application.
DOC
  step "replacement instructions written"
  write_notices "$bundle" "$notices_src"
}

# libopus and libvpx are BSD-3-Clause, which requires their notices to ship
# with any binary that contains them. Both are compiled into libavcodec here.
write_notices() {
  local bundle="$1" src="$2" out="$1/THIRD-PARTY-NOTICES.txt" f
  local bar="=============================================================================="
  if [ -n "$src" ]; then
    for f in "$src/opus-${OPUS_VERSION}/COPYING" "$src/libvpx-${VPX_VERSION}/LICENSE" "$src/libvpx-${VPX_VERSION}/PATENTS"; do
      case "$f" in
        *opus*) if [ "$WITH_OPUS" != "1" ]; then continue; fi ;;
        *)      if [ "$WITH_VPX" != "1" ]; then continue; fi ;;
      esac
      if [ ! -f "$f" ]; then die "notice source missing: $f"; fi
    done
    {
      printf 'THIRD-PARTY NOTICES\n\n'
      printf 'FFmpeg itself is LGPL-2.1-or-later; its licence is COPYING.LGPLv2.1.\n'
      printf 'The components below are compiled statically into libavcodec, and each\n'
      printf 'licence requires this notice to travel with the binaries.\n\n'
      if [ "$WITH_OPUS" = "1" ]; then
        printf '%s\nlibopus %s (COPYING)\n%s\n' "$bar" "$OPUS_VERSION" "$bar"
        cat "$src/opus-${OPUS_VERSION}/COPYING"; printf '\n'
      fi
      if [ "$WITH_VPX" = "1" ]; then
        printf '%s\nlibvpx %s (LICENSE)\n%s\n' "$bar" "$VPX_VERSION" "$bar"
        cat "$src/libvpx-${VPX_VERSION}/LICENSE"; printf '\n'
        printf '%s\nlibvpx %s (PATENTS)\n%s\n' "$bar" "$VPX_VERSION" "$bar"
        cat "$src/libvpx-${VPX_VERSION}/PATENTS"
      fi
    } > "$out"
    step "THIRD-PARTY-NOTICES.txt written from the sources that were compiled in"
  elif [ -f "$out" ]; then
    step "THIRD-PARTY-NOTICES.txt already in the bundle"
  else
    step "note: no THIRD-PARTY-NOTICES.txt here. The libopus and libvpx notices must ship"
    step "      with these binaries; formcut's binaries/ folder carries them."
  fi
}

write_manifest() {
  local bundle="$1" triple="$2" prefix="$3"
  local listing="" libs="" f cfgline sha prefix_json

  sha="$(ffmpeg_sha256_for "$FFMPEG_VERSION")"
  if [ -n "$FFMPEG_SHA256_OVERRIDE" ]; then sha="$FFMPEG_SHA256_OVERRIDE"; fi

  # An unknown prefix is recorded as null rather than as a placeholder path,
  # so a verifier can say it cannot check rather than reporting a pass.
  if [ -z "$prefix" ] || [ "$prefix" = "unknown" ]; then
    prefix_json="null"
  else
    prefix_json="\"${prefix}\""
  fi

  # Prefer the line the binary reports over one reconstructed from this
  # script: in repair mode the reconstruction is a guess, and a manifest that
  # misstates the configure line fails the obligation it exists to satisfy.
  if [ -f "$bundle/BUILDCONF.txt" ]; then
    cfgline="$(sed -n 's/^[[:space:]]*--/--/p' "$bundle/BUILDCONF.txt" \
               | tr '\n' ' ' | sed 's/\\/\\\\/g; s/"/\\"/g')"
    step "configure line read from BUILDCONF.txt, as the binary reports it"
  else
    cfgline="$(configure_flags "$prefix" "<deps>" "$ARCH" | tr '\n' ' ' | sed 's/"/\\"/g')"
  fi

  while IFS= read -r f; do
    listing="$listing    {\"path\": \"${f#"$bundle"/}\", \"sha256\": \"$(shasum -a 256 "$f" | cut -d' ' -f1)\", \"bytes\": $(wc -c < "$f" | tr -d ' ')},
"
  done < <(find "$bundle" -type f ! -name MANIFEST.json | sort)
  listing="$(printf '%s' "$listing" | sed '$ s/,$//')"

  if [ "$WITH_OPUS" = "1" ]; then
    libs="$libs    {\"name\": \"libopus\", \"version\": \"${OPUS_VERSION}\", \"licence\": \"BSD-3-Clause\", \"linkage\": \"static\", \"source_sha256\": \"${OPUS_SHA256}\"},
"
  fi
  if [ "$WITH_VPX" = "1" ]; then
    libs="$libs    {\"name\": \"libvpx\", \"version\": \"${VPX_VERSION}\", \"licence\": \"BSD-3-Clause\", \"linkage\": \"static\", \"source_sha256\": \"${VPX_SHA256}\"},
"
  fi
  libs="$(printf '%s' "$libs" | sed '$ s/,$//')"

  cat > "$bundle/MANIFEST.json" <<JSON
{
  "produced_by": "build_ffmpeg_lgpl_macos ${VERSION}",
  "built_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "triple": "${triple}",
  "deployment_target": "${DEPLOYMENT_TARGET}",
  "build_host": "$(sw_vers -productVersion 2>/dev/null || echo unknown) $(uname -m)",
  "build_prefix": ${prefix_json},
  "ffmpeg": {
    "version": "${FFMPEG_VERSION}",
    "source_url": "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz",
    "source_sha256": "${sha}",
    "licence": "LGPL-2.1-or-later",
    "configure": "${cfgline}"
  },
  "bundled_libraries": [
${libs}
  ],
  "files": [
${listing}
  ]
}
JSON
  step "MANIFEST.json written, build_prefix recorded so a verifier can refuse a false pass"
}

# ---------------------------------------------------------------------------
# Clean-room verification and packaging
# ---------------------------------------------------------------------------

cleanroom_verify() {
  local tarball="$1" triple="$2" room b read_back

  say "clean-room verification"
  room="$(mktemp -d /tmp/ffmpeg-lgpl-cleanroom.XXXXXX)"
  tar xzf "$tarball" -C "$room"
  b="$room/ffmpeg-lgpl-$triple"
  if [ ! -d "$b" ]; then b="$room"; fi

  step "extracted to $b"
  step "running under env -i so no DYLD_ variable can mask a broken path"

  if ! env -i "$b/ffmpeg-$triple" -hide_banner -version >/dev/null 2>&1; then
    env -i "$b/ffmpeg-$triple" -hide_banner -version >&2 || true
    die "ffmpeg will not start from the extracted bundle"
  fi
  if ! env -i "$b/ffprobe-$triple" -hide_banner -version >/dev/null 2>&1; then
    die "ffprobe will not start from the extracted bundle"
  fi
  if ! env -i "$b/ffmpeg-$triple" -hide_banner -loglevel error -y \
        -f lavfi -i testsrc=size=320x180:rate=30:duration=2 \
        -c:v mpeg4 "$b/probe.mp4" >/dev/null 2>&1; then
    die "ffmpeg cannot encode from the extracted bundle"
  fi

  read_back="$(env -i "$b/ffprobe-$triple" -v error -select_streams v:0 \
      -show_entries stream=codec_name,width,height -of csv=p=0 "$b/probe.mp4")"
  if [ "$read_back" != "mpeg4,320,180" ]; then
    die "ffprobe read back '$read_back', expected mpeg4,320,180"
  fi

  step "started, encoded a clip and read it back: $read_back"
  rm -rf "$room"
}

package() {
  local bundle="$1" triple="$2" out="$3"
  local name="ffmpeg-lgpl-$triple" stage

  say "packaging"
  stage="$(mktemp -d /tmp/ffmpeg-lgpl-stage.XXXXXX)"
  mkdir -p "$stage/$name"
  ( cd "$bundle" && tar cf - . ) | ( cd "$stage/$name" && tar xf - )
  ( cd "$stage" && tar czf "$out/$name.tar.gz" "$name" )
  rm -rf "$stage"
  step "$out/$name.tar.gz  ($(du -h "$out/$name.tar.gz" | cut -f1))"
}

# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

do_build() {
  local want_sha work src arches a triple prefix deps bundle built=""

  preflight

  want_sha="$(ffmpeg_sha256_for "$FFMPEG_VERSION")"
  if [ -n "$FFMPEG_SHA256_OVERRIDE" ]; then want_sha="$FFMPEG_SHA256_OVERRIDE"; fi
  if [ -z "$want_sha" ]; then
    die "FFmpeg ${FFMPEG_VERSION} is not in the pinned checksum table. Pass
    --ffmpeg-sha256 with a checksum you verified yourself, or use 7.1.1, 7.1.5
    or 9.0.2."
  fi

  work="$(mktemp -d /tmp/ffmpeg-lgpl-build.XXXXXX)"
  src="$work/src"
  mkdir -p "$src" "$OUT_DIR"

  say "sources"
  fetch "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz" \
        "$src/ffmpeg-${FFMPEG_VERSION}.tar.xz" "$want_sha"
  if [ "$WITH_OPUS" = "1" ]; then
    fetch "$OPUS_URL" "$src/opus-${OPUS_VERSION}.tar.gz" "$OPUS_SHA256"
  fi
  if [ "$WITH_VPX" = "1" ]; then
    fetch "$VPX_URL" "$src/libvpx-${VPX_VERSION}.tar.gz" "$VPX_SHA256"
  fi

  arches="$ARCH"
  if [ "$ARCH" = "both" ]; then arches="arm64 x86_64"; fi

  for a in $arches; do
    triple="$(triple_for "$a")"
    prefix="$work/install-$a"
    deps="$work/deps-$a"
    bundle="$work/bundle-$a"
    mkdir -p "$prefix" "$deps"
    rm -rf "$bundle"

    build_deps "$a" "$deps" "$src"
    build_ffmpeg "$a" "$prefix" "$deps" "$src" "$work"

    assemble "$prefix" "$bundle" "$triple" "$LIB_SOURCE"
    relocate "$bundle" "$triple"
    resign "$bundle" "$triple"
    gate_paths "$bundle"
    gate_minos "$bundle" "$DEPLOYMENT_TARGET"
    gate_licence_binary "$bundle" "$triple"
    write_documents "$bundle" "$triple" "$src/ffmpeg-${FFMPEG_VERSION}/COPYING.LGPLv2.1" "$src"
    write_manifest "$bundle" "$triple" "$prefix"

    rm -rf "$OUT_DIR/ffmpeg-lgpl-$triple"
    mkdir -p "$OUT_DIR/ffmpeg-lgpl-$triple"
    ( cd "$bundle" && tar cf - . ) | ( cd "$OUT_DIR/ffmpeg-lgpl-$triple" && tar xf - )
    package "$bundle" "$triple" "$OUT_DIR"
    built="$built $a"
  done

  if [ "$KEEP_BUILD" = "1" ]; then
    say "build tree kept at $work"
    step "verification SKIPPED on purpose. A bundle checked while its build tree"
    step "still exists proves nothing, which is how the last one passed."
  else
    say "deleting the build tree, then verifying"
    step "$work"
    rm -rf "$work"
    for a in $built; do
      triple="$(triple_for "$a")"
      cleanroom_verify "$OUT_DIR/ffmpeg-lgpl-$triple.tar.gz" "$triple"
    done
  fi

  say "done"
  ls -la "$OUT_DIR" | awk 'NR > 1 { printf "   %10s  %s\n", $5, $9 }'
}

do_repair() {
  local triple bundle libdir search l base real

  preflight
  if [ ! -d "$OUT_DIR" ]; then die "--out $OUT_DIR does not exist"; fi
  triple="$(triple_for "$ARCH")"
  if [ ! -f "$OUT_DIR/ffmpeg-$triple" ]; then
    die "no ffmpeg-$triple in $OUT_DIR"
  fi

  say "repair mode, nothing is compiled"
  if [ -n "$LIB_SOURCE" ]; then
    step "missing libraries will be looked for under $LIB_SOURCE"
  else
    step "no --lib-source given; only libraries already present can be used"
  fi

  bundle="$OUT_DIR"
  libdir="$bundle/lib-$triple"
  mkdir -p "$libdir"

  # Any symlink already in the bundle becomes the file it points at, or is
  # removed and re-pulled. This is the defect that produced a tarball whose
  # library entries were links to nothing.
  while IFS= read -r l; do
    base="$(basename "$l")"
    if real="$(resolve_link "$l")" && [ -f "$real" ]; then
      rm -f "$l"
      cp -f "$real" "$l"
      chmod u+w "$l"
      step "replaced link $base with its target"
    else
      rm -f "$l"
      step "removed dangling link $base"
    fi
  done < <(find "$bundle" -type l -print)

  search="$libdir"
  if [ -n "$LIB_SOURCE" ]; then
    search="$search
$LIB_SOURCE
$LIB_SOURCE/lib"
  fi
  close_dependencies "$bundle" "$libdir" "$search"

  relocate "$bundle" "$triple"
  resign "$bundle" "$triple"
  gate_paths "$bundle"
  gate_minos "$bundle" "$DEPLOYMENT_TARGET"
  gate_licence_binary "$bundle" "$triple"
  write_documents "$bundle" "$triple" "$LICENCE_FILE"
  write_manifest "$bundle" "$triple" ""
  package "$bundle" "$triple" "$OUT_DIR"
  cleanroom_verify "$OUT_DIR/ffmpeg-lgpl-$triple.tar.gz" "$triple"
  say "repaired"
}

do_verify() {
  local triple
  if [ -z "$TARBALL" ]; then die "--verify-only needs --tarball FILE.tar.gz"; fi
  if [ ! -f "$TARBALL" ]; then die "$TARBALL does not exist"; fi
  triple="$(triple_for "$ARCH")"
  cleanroom_verify "$TARBALL" "$triple"
  say "verified"
}

main() {
  case "$MODE" in
    build)  do_build ;;
    repair) do_repair ;;
    verify) do_verify ;;
  esac
}

if [ "${FFLGPL_SOURCE_ONLY:-0}" != "1" ]; then
  main
fi
