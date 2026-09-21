# ffmpeg in this bundle

formcut ships **LGPL-2.1-or-later** builds of FFmpeg 7.1.5, configured with
`--disable-gpl --disable-nonfree --disable-version3`. formcut itself stays
**Apache-2.0**: it runs ffmpeg as a separate program rather than linking against
it, so the two licences meet at a process boundary and neither reaches across it.

`ffmpeg-licence.json` is the record for everything in this folder: the exact
configure line of each build (read from the binary, not retyped), the source
tarballs and their SHA-256, the toolchain, how each target was verified, and the
SHA-256 of every file. If this README and that record ever disagree, the record
is right and this file is stale.

## What is here

| Target | Programs | Libraries | Found by | Verified |
| --- | --- | --- | --- | --- |
| `aarch64-apple-darwin` | `ffmpeg-…`, `ffprobe-…` | `lib-aarch64-apple-darwin/`, 7 dylibs | `@rpath`, via `@executable_path/lib-…` | load commands read; run on the build Mac |
| `x86_64-unknown-linux-gnu` | `ffmpeg-…`, `ffprobe-…` | `lib-x86_64-unknown-linux-gnu/`, 7 `.so` | `RUNPATH $ORIGIN/lib-…` | executed in a clean room |
| `x86_64-pc-windows-msvc` | `ffmpeg-….exe`, `ffprobe-….exe` | `lib-x86_64-pc-windows-msvc/`, 7 DLLs | Windows DLL search order | imports checked; not executed |
| `x86_64-apple-darwin` | `ffmpeg-…`, `ffprobe-…` | `lib-x86_64-apple-darwin/`, 7 dylibs | `@rpath`, via `@executable_path/lib-…` | executed in a clean room |

Every target is the same FFmpeg source with libvpx 1.17.0 and libopus 1.6.1
compiled into libavcodec, so VP9 (including alpha) and Opus encode everywhere.
Nothing in any build comes from Homebrew or a system package manager.

## The one layout rule

The programs find their libraries relative to where the programs themselves
sit, and the rule differs by platform:

- **macOS and Linux:** the two programs and their `lib-<triple>/` directory must
  stay siblings wherever they are installed. Move one without the others and the
  program will not start.
- **Windows:** there is no rpath. At run time the seven DLLs must sit in the
  same directory as the `.exe`, or their directory must be on the `PATH` of the
  process formcut spawns. Setting the child's `PATH` is the more robust of the
  two, because it does not depend on where the packager puts files.

formcut does not bundle these into its desktop app. It looks for them, in order,
in `FORMCUT_FFMPEG_DIR`, beside a packaged app, in a per-person folder, and in
`src-tauri/binaries` in a clone, and otherwise runs the `ffmpeg` on `PATH`. The
per-person folder is `~/Library/Application Support/formcut/ffmpeg` on macOS,
`%LOCALAPPDATA%\formcut\ffmpeg` on Windows and `~/.local/share/formcut/ffmpeg`
on Linux. It is the place to put this folder by hand, because adding files
inside a signed macOS app breaks its seal. On Windows formcut puts the
`lib-<triple>/` folder on the `PATH` of everything it runs.

## Replacing it

You may swap these binaries for your own build. That is a right the LGPL gives
you, and nothing here is arranged to make it difficult. Replace a library with a
build of the same major version under the same file name. On macOS a replaced
library needs the install name `@rpath/<name>` and a signature:

    install_name_tool -id @rpath/libavcodec.61.dylib libavcodec.61.dylib
    codesign --force --sign - libavcodec.61.dylib

formcut puts the folder it uses at the front of its search path, so whatever is
there is what runs. Where only `ffmpeg-<triple>` is present, formcut gives it its
plain name alongside: a symlink on macOS and Linux, a hard link or a copy on
Windows. A file already named `ffmpeg` is never touched, so a program you put
there yourself is the one that runs. To point formcut somewhere else entirely,
set `FORMCUT_FFMPEG_DIR`.

## Source and notices

The LGPL requires that anyone receiving these binaries can obtain the exact
source. All four shipped targets were built from one tarball, recorded with its
SHA-256 in `ffmpeg-licence.json` along with the libopus and libvpx tarballs.
FFmpeg's legal checklist asks distributors to host that source themselves beside
the download, not only to link to ffmpeg.org.

libopus, libvpx and (on Windows) winpthreads are compiled into FFmpeg's
libraries, and their licences require their notices to travel with the
binaries. Those are in `THIRD-PARTY-NOTICES.txt`. The FFmpeg licence is
`LGPL-2.1.txt`, taken byte-for-byte from the FFmpeg source.

## Reading alpha back from VP9

FFmpeg's native VP9 decoder ignores the alpha channel. To decode it, force the
libvpx decoder before the input:

    ffmpeg -c:v libvpx-vp9 -i input.webm ...

## Rebuilding Linux and Windows

Three things fail confusingly when rebuilding these, all found producing this
folder:

- `opus.pc` keeps `-lm` in `Libs.private`, so configure rejects a static libopus
  unless it is given `--pkg-config-flags=--static`.
- On Linux, static dependencies must be compiled with `-fPIC`, or linking them
  into the shared `libavcodec.so` fails.
- When cross-compiling, configure looks for a prefixed `pkg-config`. If it is
  missing, configure substitutes `false` and reports "opus not found" instead
  of saying why. Pass `--pkg-config=pkg-config`.

On Windows, libvpx pulls in the mingw-w64 threading runtime. Unless it is linked
statically, the build depends on `libwinpthread-1.dll`, which Windows does not
have. `ffmpeg-licence.json` records how this build handled it.
