# src-tauri/ffmpeg

The release workflow fills this folder for the macOS and Windows installers with
formcut's LGPL ffmpeg from the formcut-binaries release, after checking every
file against `src-tauri/binaries/ffmpeg-licence.json`. The programs are staged
under their plain names, `ffmpeg` and `ffprobe`, beside their `lib-<triple>`
folder, so an installed app, which cannot be written to, needs no links made.

In a clone it holds only this file, and the app finds ffmpeg as it always has:
`FORMCUT_FFMPEG_DIR`, the per-person folder, `src-tauri/binaries`, PATH, or a
first-run fetch. Linux packages are built without it, because an ffmpeg
installed into `/usr/bin` by a package would collide with the system's own.
