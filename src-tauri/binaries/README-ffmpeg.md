# ffmpeg in this bundle

formcut ships **LGPL-2.1** builds of ffmpeg, configured with `--disable-gpl
--disable-nonfree`. formcut itself stays **Apache-2.0**: it runs ffmpeg as a
separate program rather than linking against it, so the two licences meet at a
process boundary and neither reaches across it.

## Replacing it

You may swap these binaries for your own build. That is a right the LGPL gives
you, and nothing here is arranged to make it difficult.

- **macOS** — right-click formcut.app, *Show Package Contents*, then
  `Contents/Resources/binaries/`. Replace `ffmpeg` (and `ffprobe` if present),
  keep the names, and make them executable: `chmod +x ffmpeg`.
- **Windows** — `binaries\` beside `formcut.exe`.
- **Linux** — `binaries/` beside the executable, or inside the AppImage's
  extracted tree.

formcut puts this folder at the front of its search path, so whatever is here is
what runs. To point it somewhere else entirely, set `FORMCUT_FFMPEG_DIR`.

## ffprobe

An LGPL build configured with `--disable-programs --enable-ffmpeg` produces
ffmpeg alone, because ffprobe is a separate program. formcut does not need it:
when ffprobe is absent it reads the same facts from ffmpeg's own report. Adding
an LGPL ffprobe here is supported and will be used in preference.

## What is here

| Target | Programs | Built how |
| --- | --- | --- |
| `aarch64-apple-darwin` | ffmpeg | supplied, `--disable-gpl --disable-nonfree --enable-videotoolbox` |
| `x86_64-unknown-linux-gnu` | ffmpeg, ffprobe | built LGPL, shared libraries in `lib-x86_64-unknown-linux-gnu` |
| `x86_64-pc-windows-msvc` | ffmpeg.exe, ffprobe.exe | cross-built with mingw-w64, DLLs in `lib-x86_64-pc-windows-msvc` |

The Linux build is **shared** rather than static, which is deliberate: the LGPL
expects you to be able to substitute your own build of the libraries, and shared
objects beside the binary are what make that possible without relinking anything.

One target left, and it needs a Mac to build on because it needs Apple's SDK:

    ./setup/build_ffmpeg_lgpl.sh        # on an Intel Mac, for x86_64-apple-darwin

## Source

The LGPL requires that you can get the source for the binary you received.
`ffmpeg-licence.json` in this folder records the exact version, the configure
line and the SHA-256 of each binary shipped. The corresponding source is
available from <https://ffmpeg.org/download.html> and, for the exact revision,
from the git tag named in that file.
