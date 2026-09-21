#!/usr/bin/env bash
#
# verify_ffmpeg_lgpl_bundle v1.0.1
#
# Checks an FFmpeg LGPL bundle produced by build_ffmpeg_lgpl_macos, or by
# anyone else. It is deliberately independent of whatever produced the bundle:
# it takes a tarball or a directory, copies it somewhere else, and asks whether
# the thing actually works there.
#
# It refuses to report a pass when the conditions that once produced a false
# pass are present, specifically a build prefix that still exists on disk.
#
#   ./verify_ffmpeg_lgpl_bundle_v1.0.0.sh path/to/ffmpeg-lgpl-<triple>.tar.gz
#   ./verify_ffmpeg_lgpl_bundle_v1.0.0.sh path/to/bundle-dir --triple aarch64-apple-darwin
#
# Options
#   --triple TRIPLE   required when the name does not carry it
#   --deployment-target X.Y   maximum acceptable minos (default: read from MANIFEST, else 11.0)
#   --allow-build-prefix      continue even if the recorded build prefix still exists
#   --keep                    leave the extracted copy in place and print where it is

set -euo pipefail

VERSION="v1.0.1"
TARGET=""
TRIPLE=""
WANT_MINOS=""
ALLOW_PREFIX=0
KEEP=0
FAILURES=0
UNCHECKED=0
ROOM=""

say()  { printf '\n== %s\n' "$*"; }
ok()   { printf '   pass  %s\n' "$*"; }
bad()  { printf '   FAIL  %s\n' "$*" >&2; FAILURES=$((FAILURES + 1)); }
note() { printf '   note  %s\n' "$*"; UNCHECKED=$((UNCHECKED + 1)); }
die()  { printf '\nREFUSING: %s\n' "$*" >&2; exit 2; }

cleanup() {
  if [ -n "$ROOM" ] && [ "$KEEP" = "0" ]; then
    chmod -R u+w "$ROOM" 2>/dev/null || true
    rm -rf "$ROOM"
  fi
}
trap cleanup EXIT

while [ $# -gt 0 ]; do
  case "$1" in
    --triple)             TRIPLE="${2:-}"; shift 2 ;;
    --deployment-target)  WANT_MINOS="${2:-}"; shift 2 ;;
    --allow-build-prefix) ALLOW_PREFIX=1; shift ;;
    --keep)               KEEP=1; shift ;;
    -h|--help)
      sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    -*) die "unknown option: $1" ;;
    *)  TARGET="$1"; shift ;;
  esac
done

if [ -z "$TARGET" ]; then die "give me a tarball or a bundle directory"; fi
if [ ! -e "$TARGET" ]; then die "$TARGET does not exist"; fi

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

json_string() {
  # json_string FILE KEY -> the first "KEY": "value" it finds, or empty
  sed -n "s/.*\"$2\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$1" | head -1
}

# ---------------------------------------------------------------------------
# Stage a copy somewhere else. Verifying in place tells you nothing about
# whether the bundle can move, which is the whole question.
# ---------------------------------------------------------------------------

say "verify_ffmpeg_lgpl_bundle $VERSION"
ROOM="$(mktemp -d /tmp/ffmpeg-lgpl-verify.XXXXXX)"

if [ -d "$TARGET" ]; then
  # Guard against being handed a parent folder. Copying an arbitrary directory
  # wholesale is how this turned into an attempt to tar up someone's Downloads.
  shape=0
  for candidate in "$TARGET"/ffmpeg-*; do
    if [ -f "$candidate" ]; then shape=1; break; fi
  done
  if [ "$shape" = "0" ]; then
    die "$TARGET does not look like a bundle: nothing named ffmpeg-<triple> in it.
    Give me the tarball (ffmpeg-lgpl-<triple>.tar.gz) or the extracted bundle
    directory itself, not the folder those live in."
  fi
  mkdir -p "$ROOM/bundle"
  ( cd "$TARGET" && tar cf - . ) | ( cd "$ROOM/bundle" && tar xf - )
  B="$ROOM/bundle"
  printf '   staged a copy of the directory at %s\n' "$B"
else
  tar xzf "$TARGET" -C "$ROOM"
  B="$(find "$ROOM" -mindepth 1 -maxdepth 1 -type d | head -1)"
  if [ -z "$B" ]; then B="$ROOM"; fi
  printf '   extracted %s to %s\n' "$(basename "$TARGET")" "$B"
fi

if [ -z "$TRIPLE" ]; then
  if [ -f "$B/MANIFEST.json" ]; then
    TRIPLE="$(json_string "$B/MANIFEST.json" triple)"
  fi
fi
if [ -z "$TRIPLE" ]; then
  TRIPLE="$(basename "$TARGET" | sed -n 's/^ffmpeg-lgpl-\(.*\)\.tar\.gz$/\1/p')"
fi
if [ -z "$TRIPLE" ]; then
  die "cannot work out the target triple. Pass --triple."
fi
printf '   triple: %s\n' "$TRIPLE"

FFMPEG="$B/ffmpeg-$TRIPLE"
FFPROBE="$B/ffprobe-$TRIPLE"
LIBDIR="$B/lib-$TRIPLE"

# ---------------------------------------------------------------------------

say "1. the build tree is gone"
if [ -f "$B/MANIFEST.json" ]; then
  PREFIX="$(json_string "$B/MANIFEST.json" build_prefix)"
  if [ -n "$PREFIX" ] && [ -d "$PREFIX" ]; then
    if [ "$ALLOW_PREFIX" = "1" ]; then
      bad "the recorded build prefix still exists at $PREFIX, continuing because --allow-build-prefix was given, but this run cannot prove the bundle is self-contained"
    else
      die "the build prefix recorded in the manifest still exists:
    $PREFIX
    dyld can resolve stale absolute paths from there, so a pass now would mean
    nothing. Delete it and run this again, or pass --allow-build-prefix if you
    understand what the result will and will not show."
    fi
  elif [ -z "$PREFIX" ] || [ "$PREFIX" = "null" ] || [ "$PREFIX" = "repaired-unknown-prefix" ]; then
    note "no build prefix recorded, so this cannot be checked here. Confirm by
         hand that the tree the bundle was built in is gone."
  else
    ok "recorded build prefix is absent: $PREFIX"
  fi
else
  bad "no MANIFEST.json, so the build prefix cannot be checked"
fi

say "2. shape"
for f in "$FFMPEG" "$FFPROBE"; do
  if [ -f "$f" ]; then ok "$(basename "$f") present"; else bad "$(basename "$f") missing"; fi
done
if [ -d "$LIBDIR" ]; then
  n="$(find "$LIBDIR" -type f | wc -l | tr -d ' ')"
  ok "lib-$TRIPLE holds $n regular file(s)"
else
  bad "lib-$TRIPLE missing"
fi
links="$(find "$B" -type l | wc -l | tr -d ' ')"
if [ "$links" = "0" ]; then
  ok "no symbolic links"
else
  bad "$links symbolic link(s); a link whose target was never copied is how the last bundle shipped empty"
  find "$B" -type l -print | sed 's/^/         /' >&2
fi
for d in COPYING.LGPLv2.1 BUILDCONF.txt README-replacing-ffmpeg.md MANIFEST.json; do
  if [ -f "$B/$d" ]; then ok "$d present"; else bad "$d missing, this is an LGPL obligation not a nicety"; fi
done

# The manifest is flattened before entries are split out, so a pretty-printed
# copy reads the same as the compact one this script writes.
say "3. recorded checksums still match"
if [ -f "$B/MANIFEST.json" ]; then
  mism=0; checked=0
  while IFS= read -r line; do
    p="$(printf '%s' "$line" | sed -n 's/.*"path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
    h="$(printf '%s' "$line" | sed -n 's/.*"sha256"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
    if [ -z "$p" ] || [ -z "$h" ]; then continue; fi
    if [ "$p" = "MANIFEST.json" ]; then
      printf '   skip  MANIFEST.json cannot record its own hash\n'
      continue
    fi
    checked=$((checked + 1))
    if [ ! -f "$B/$p" ]; then bad "manifest lists $p but it is not there"; mism=$((mism + 1)); continue; fi
    got="$(shasum -a 256 "$B/$p" | cut -d' ' -f1)"
    if [ "$got" != "$h" ]; then bad "$p does not match its recorded sha256"; mism=$((mism + 1)); fi
  done < <(tr '\n' ' ' < "$B/MANIFEST.json" | tr '}' '\n' | grep '"path"')
  if [ "$checked" -gt 0 ] && [ "$mism" -eq 0 ]; then ok "$checked file(s) match the manifest"; fi
  if [ "$checked" -eq 0 ]; then bad "the manifest lists no files"; fi
fi

say "4. no dependency points outside the bundle"
leaks=0
while IFS= read -r f; do
  if ! file -b "$f" 2>/dev/null | grep -q 'Mach-O'; then continue; fi
  while IFS= read -r dep; do
    case "$dep" in
      /usr/lib/*|/System/Library/*) continue ;;
      @rpath/*|@loader_path/*|@executable_path/*) continue ;;
    esac
    bad "$(basename "$f") -> $dep"
    leaks=$((leaks + 1))
  done < <(otool -L "$f" | awk 'NR > 1 { print $1 }')
done < <(find "$B" -type f -print)
if [ "$leaks" -eq 0 ]; then ok "every dependency is a system path or relative to the bundle"; fi

say "5. every @rpath dependency actually resolves"
unres=0
while IFS= read -r f; do
  if ! file -b "$f" 2>/dev/null | grep -q 'Mach-O'; then continue; fi
  while IFS= read -r dep; do
    case "$dep" in
      @rpath/*) base="${dep#@rpath/}" ;;
      *) continue ;;
    esac
    if [ ! -f "$LIBDIR/$base" ]; then
      bad "$(basename "$f") needs $base and lib-$TRIPLE does not have it"
      unres=$((unres + 1))
    fi
  done < <(otool -L "$f" | awk 'NR > 1 { print $1 }')
done < <(find "$B" -type f -print)
if [ "$unres" -eq 0 ]; then ok "all @rpath entries have a file behind them"; fi

say "6. signatures are valid"
sig=0
while IFS= read -r f; do
  if ! file -b "$f" 2>/dev/null | grep -q 'Mach-O'; then continue; fi
  if ! codesign --verify "$f" >/dev/null 2>&1; then
    bad "$(basename "$f") has an invalid signature; on Apple Silicon it will be killed on launch"
    sig=$((sig + 1))
  fi
done < <(find "$B" -type f -print)
if [ "$sig" -eq 0 ]; then ok "every Mach-O verifies"; fi

say "7. minimum macOS"
if [ -z "$WANT_MINOS" ] && [ -f "$B/MANIFEST.json" ]; then
  WANT_MINOS="$(json_string "$B/MANIFEST.json" deployment_target)"
fi
if [ -z "$WANT_MINOS" ]; then WANT_MINOS="11.0"; fi
high=0
while IFS= read -r f; do
  if ! file -b "$f" 2>/dev/null | grep -q 'Mach-O'; then continue; fi
  got="$(otool -l "$f" | awk '/LC_BUILD_VERSION/ { b = 1 } b && /^ *minos/ { print $2; b = 0 }' | head -1)"
  if [ -z "$got" ]; then
    got="$(otool -l "$f" | awk '/LC_VERSION_MIN_MACOSX/ { b = 1 } b && /^ *version/ { print $2; b = 0 }' | head -1)"
  fi
  if [ -z "$got" ]; then continue; fi
  if ! ver_le "$got" "$WANT_MINOS"; then
    bad "$(basename "$f") requires macOS $got, above the stated $WANT_MINOS"
    high=$((high + 1))
  fi
done < <(find "$B" -type f -print)
if [ "$high" -eq 0 ]; then ok "nothing requires more than macOS $WANT_MINOS"; fi

say "8. licence"
if [ -x "$FFMPEG" ]; then
  conf="$(env -i "$FFMPEG" -hide_banner -buildconf 2>&1 || true)"
  if printf '%s' "$conf" | grep -qE 'enable-gpl|enable-nonfree|libx264|libx265|libfdk'; then
    bad "buildconf reports a GPL or nonfree component; this binary cannot ship in a proprietary bundle"
    printf '%s\n' "$conf" | grep -E 'enable-gpl|enable-nonfree|libx264|libx265|libfdk' | sed 's/^/         /' >&2
  else
    ok "no gpl, nonfree, x264, x265 or fdk in buildconf"
  fi
  # FFmpeg wraps this notice across lines, so it is flattened before matching.
  lic="$(env -i "$FFMPEG" -hide_banner -L 2>&1 | head -20 | tr '\n' ' ' || true)"
  if printf '%s' "$lic" | grep -qi 'Lesser General Public'; then
    ok "the binary reports the Lesser GPL"
  else
    bad "the binary does not report the Lesser GPL"
  fi
fi

say "9. it runs, encodes and reads back, with a scrubbed environment"
if [ -x "$FFMPEG" ] && [ -x "$FFPROBE" ]; then
  if env -i "$FFMPEG" -hide_banner -version >/dev/null 2>&1; then
    ok "ffmpeg starts under env -i"
  else
    bad "ffmpeg will not start. dyld output follows:"
    env -i "$FFMPEG" -hide_banner -version 2>&1 | head -10 | sed 's/^/         /' >&2
  fi
  if env -i "$FFPROBE" -hide_banner -version >/dev/null 2>&1; then
    ok "ffprobe starts under env -i"
  else
    bad "ffprobe will not start"
  fi
  if env -i "$FFMPEG" -hide_banner -loglevel error -y \
       -f lavfi -i testsrc=size=320x180:rate=30:duration=2 \
       -c:v mpeg4 "$ROOM/probe.mp4" >/dev/null 2>&1; then
    ok "encoded a two second clip"
    rb="$(env -i "$FFPROBE" -v error -select_streams v:0 \
          -show_entries stream=codec_name,width,height -of csv=p=0 "$ROOM/probe.mp4" 2>/dev/null || true)"
    if [ "$rb" = "mpeg4,320,180" ]; then
      ok "read it back: $rb"
    else
      bad "read back '$rb', expected mpeg4,320,180"
    fi
  else
    bad "cannot encode"
  fi
fi

say "10. optional codecs, reported not judged"
if [ -x "$FFMPEG" ]; then
  enclist="$(env -i "$FFMPEG" -hide_banner -encoders 2>/dev/null | awk 'NF >= 2 { print $2 }' || true)"
  for enc in libvpx-vp9 libopus h264_videotoolbox hevc_videotoolbox aac; do
    if printf '%s\n' "$enclist" | grep -qxF "$enc"; then
      printf '   have  %s\n' "$enc"
    else
      printf '   none  %s\n' "$enc"
    fi
  done
fi

say "result"
if [ "$KEEP" = "1" ]; then printf '   staged copy left at %s\n' "$ROOM"; fi
if [ "$FAILURES" -eq 0 ]; then
  printf '   PASS. The bundle works from a location it was not built in.\n'
  if [ "$UNCHECKED" -gt 0 ]; then
    printf '   %d check(s) could not be run; see the notes above.\n' "$UNCHECKED"
  fi
  printf '\n'
  exit 0
fi
printf '   FAIL, %d problem(s) above.\n\n' "$FAILURES"
exit 1
