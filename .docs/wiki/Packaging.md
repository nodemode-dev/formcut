# Packaging and persistence

Releases are made by hand: after the version is bumped on `main`, running the release workflow on `main` (Actions, release, Run workflow) makes `.github/workflows/release.yml` build macOS (Apple silicon), Windows (x86_64) and Linux (x86_64) and publish one zip for each, with `SHA256SUMS` and `manifest.json`, on the release `v<version>`; see [RELEASING.md](https://github.com/nodemode-ai/formcut/blob/main/RELEASING.md). To build on your own machine, use the host-native script: `setup/build_macos_app` (with `--intel` for Intel Macs, on any Mac), `setup/build_linux_app`, `setup/build_windows_app.bat`, `setup/build_macos_portable`, `setup/build_windows_portable.bat` or `setup/build_portable_linux`. The app scripts build the frontend, build formcut's Rust kernels and refuse an engine frozen without them, freeze the engine with `backend/freeze.py`, bundle formcut's verified LGPL ffmpeg with `setup/bundle_ffmpeg.py`, build the app, and write its release zip with `setup/package_release.py`.

App bundles freeze the engine to one file, portable folders to one directory. The app bundles carry formcut's ffmpeg; the portable folders use an ffmpeg on PATH or formcut's first-run download. Model weights and the optional speech environment are not included in the distributable.

Day to day, the repository root carries one launcher per platform: `./formcut` and `formcut.bat` only sequence the three scripts in `setup/`, which are the banner, an idempotent install and the boot. Each of those resolves the repository root itself, so they work from any working directory; the install step creates `.env` from `example.env` when it is missing, and the boot step exports `.env` before starting either half and refuses to start when the engine or the interface is not installed yet.

The build scripts run `backend/prepare_cv.py` before freezing. Standard OpenCV wheels contain FFmpeg libraries, so this step compiles an image-processing-only OpenCV runtime with those backends disabled. A C++ compiler and source-build prerequisites are required; the first build can take several minutes. `freeze.py` refuses a codec-enabled OpenCV installation. Keep the notices copied into the frozen output.

The Tauri shell launches the engine on port zero, parses its bind line, checks health with a timeout and opens a window using the monitor's scale factor. It drains process events after startup and terminates the engine on quit. The Rust crate compiles: `cargo check` finishes clean once the frontend is built and the frozen engine binary is in place, both of which the build scripts produce. A full bundle and the native window, menu and quit lifecycle still need acceptance on macOS and Windows.

Default writable data roots:

| Platform | Location |
| --- | --- |
| macOS | `~/Library/Application Support/formcut` |
| Windows | `%LOCALAPPDATA%/formcut` |
| Linux | `$XDG_DATA_HOME/formcut`, otherwise `~/.local/share/formcut` |
| Frozen portable build | `portable/` beside the engine executable, when that directory exists |
| Explicit override | `FORMCUT_DATA_DIR` |

Portable scripts now create `engine/portable`. They refuse to replace an existing portable folder containing that directory, to preserve user data. Move or back up an existing portable folder before rebuilding.

There is no automatic migration from older `backend/data` installations. To retain an existing library, set FORMCUT_DATA_DIR to that directory before launching or copy its contents into the selected new data root while the app is stopped. Preserve projects, media indexes, media files and thumbnails together. Back up before migrating.

`FORMCUT_DIST` points to a built frontend only. `FORMCUT_FONT_PATH` selects a fallback text font. `FORMCUT_AI_PYTHON` selects an external speech interpreter; otherwise setup_local_ai creates one under the data root. Never point a frozen speech subprocess at the frozen engine itself.

Onefile and onedir builds are platform-specific. A Linux freeze is not a macOS app, Windows installer or mobile build. Android/iOS need a mobile engine, not the desktop sidecar configuration; see [Mobile notes](Mobile-notes.md).
