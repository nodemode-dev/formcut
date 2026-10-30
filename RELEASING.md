# Releasing formcut

A release is a version, and only the maintainer makes one. formcut builds
nothing in its own repository: nodemode-ai/formcompiler builds every form* app
and opens a draft release on its own release page
(https://github.com/nodemode-ai/formcompiler/releases), which the maintainer
reviews and publishes. This repository supplies the build scripts
(`setup/build_release`, `setup/build_phone`, `setup/release_assets`).

## Before releasing

Bump the version at every site in one `chore(release)` commit, then run:

```sh
python setup/preflight.py
```

It refuses a version that disagrees anywhere, a build that refers to a missing
file, or an ffmpeg licence that has not been decided.

## Making the release

Push the `chore(release)` commit to `main` and wait for the checks to pass
(`.github/rulesets/main.json` still applies to them). Then push a branch cut from
main's head:

```sh
git push origin main:refs/heads/compile_vX.Y.Z
```

1. **Pick-up.** nodemode-ai/formcompiler watches for `compile_v*` branches every
   eight hours, or on a manual run, and builds the version on the branch.
2. **Five builds, side by side:** macOS on Apple silicon, Windows x86_64, and
   Linux x86_64 (on Ubuntu 22.04, so the AppImage runs on glibc 2.35 and newer),
   each by `setup/build_release --target TRIPLE`, and the Android and iOS
   companion apps by `setup/build_phone`.
   Each desktop build makes the interface, then the engine with formcut's Rust
   kernels (an engine without them is refused), OpenCV rebuilt without its own
   FFmpeg, formcut's verified LGPL ffmpeg from nodemode-ai/formcut-binaries, the
   app, and one zip (`setup/package_release.py`); on Windows the app is built
   with `--bundles nsis` and its installer is released beside the zip.
3. **One draft.** `setup/release_assets` writes `SHA256SUMS`, `manifest.json` and
   notes from `setup/release_notes.py`: a download table, how to open each app,
   and the commits since the last release. formcompiler opens a draft release
   `formcut-vX.Y.Z` on its release page with every file. The maintainer reviews
   the draft and publishes it.

| Zip | Holds |
| --- | --- |
| `formcut-<version>-macos-arm64.zip` | formcut.app |
| `formcut-<version>-windows-x86_64-setup.exe` | the NSIS installer: formcut.exe, formcut-engine.exe and ffmpeg, installed in that layout |
| `formcut-<version>-windows-x86_64.zip` | a formcut folder: formcut.exe, formcut-engine.exe and ffmpeg beside them |
| `formcut-<version>-linux-x86_64.zip` | the AppImage |
| `formcut-<version>-android-arm64.apk` | the Android companion, signed with the debug key |
| `formcut-<version>-ios-arm64.ipa` | the iOS companion, unsigned |

## If a build fails

No draft is opened, so nothing half-finished is published. Fix it, push the fix
to `main`, and push a new `compile_vX.Y.Z` branch cut from main's head (or ask
formcompiler for a manual run); the version is built again.

## Building a zip locally

`setup/build_macos_app` (with `--intel` for Intel Macs) and
`setup/build_linux_app` build the app and write the same zip to `release-dist/`
through `setup/package_release.py`. Intel Macs are not built by the release.

## Signing

formcut signs nothing with its own keys; formcompiler holds them.

- **macOS.** When formcompiler has the Apple identity, `setup/build_release`
  gets `APPLE_SIGNING_IDENTITY` (and `APPLE_ID`, `APPLE_PASSWORD`,
  `APPLE_TEAM_ID`). It signs the bundled ffmpeg programs and libraries with that
  Developer ID, hardened runtime and a timestamp, and Tauri signs formcut and the
  engine sidecar the same way with `src-tauri/entitlements.plist`, then
  notarizes and staples the app. The release checks the app unzipped from its
  own zip for the Developer ID, its team and hardened runtime, and runs
  `stapler validate` and `spctl` when it was notarized. Without the identity the
  app is signed ad hoc (`signingIdentity: "-"` in `tauri.conf.json`), which
  needs no Apple account and seals the bundle (without a seal macOS calls a
  downloaded app damaged and offers no way to open it); the release checks that
  seal instead, and the first launch goes through System Settings, Privacy &
  Security, Open Anyway, as the release notes say.
- **Windows.** formcompiler writes `tauri.windows.conf.json` beside
  `tauri.conf.json` before the build, so Tauri signs formcut.exe, the engine
  sidecar and the NSIS installer, and it signs whatever is still unsigned in
  the zip afterwards. Nothing in this repository signs Windows files.
