# Releasing formcut

A release is a version, and only the maintainer makes one. No push starts a
release: the release workflow (`.github/workflows/release.yml`) runs only when
started by hand, and only from `main`.

## Before releasing

Bump the version at every site in one `chore(release)` commit, then run:

```sh
python setup/preflight.py
```

It refuses a version that disagrees anywhere, a build that refers to a missing
file, or an ffmpeg licence that has not been decided.

## Making the release

Push the `chore(release)` commit to `main` and wait for the checks to pass. Then
start the release: Actions, release, Run workflow on `main`, or

```sh
gh workflow run release.yml --ref main
```

1. **Which version.** The workflow reads `APP_VERSION`. If `v<version>` is not
   tagged yet, it builds. A version already released builds nothing, unless the
   run is started with **rebuild**, which builds it again and replaces its files.
   Started from any branch but `main`, it stops.
2. **Five builds, side by side:** macOS on Apple silicon, Windows x86_64, and
   Linux x86_64 (on Ubuntu 22.04, so the AppImage runs on glibc 2.35 and newer),
   and the Android and iOS companion apps.
   Each builds the interface, then the engine with formcut's Rust kernels (an
   engine without them is refused), OpenCV rebuilt without its own FFmpeg,
   formcut's verified ffmpeg from formcut-binaries, the app, and one zip
   (`setup/package_release.py`).
3. **One release.** Only when all five succeed, `v<version>` is tagged and the
   release published with every file, `SHA256SUMS`, `manifest.json`, and notes
   from `setup/release_notes.py`: a download table, how to open each app, and the
   commits since the last release.

| Zip | Holds |
| --- | --- |
| `formcut-<version>-macos-arm64.zip` | formcut.app |
| `formcut-<version>-windows-x86_64.zip` | a formcut folder: formcut.exe, formcut-engine.exe and ffmpeg beside them |
| `formcut-<version>-linux-x86_64.zip` | the AppImage |
| `formcut-<version>-android-arm64.apk` | the Android companion, signed with the debug key |
| `formcut-<version>-ios-arm64.ipa` | the iOS companion, unsigned |

## If a build fails

No tag is made, so nothing half-finished is published. Fix it, push the fix to
`main`, and run the workflow again: the version is still untagged, so it builds.
To replace the files of a version that is already released, run it with
**rebuild**.

## Building a zip locally

`setup/build_macos_app` (with `--intel` for Intel Macs) and
`setup/build_linux_app` build the app and write the same zip to `release-dist/`
through `setup/package_release.py`. Intel Macs are not built by the workflow.

## Signing

The apps are unsigned; the release notes say how to open each the first time.
Signing would go in the "build the app" step: an Apple Developer identity for
notarization, a code-signing certificate for Windows.
