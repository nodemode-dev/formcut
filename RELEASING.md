# Releasing formcut

A release is a version. Bump it, push to `main`, and the release workflow
(`.github/workflows/release.yml`) builds and publishes the rest.

## Before pushing

Bump the version at every site in one `chore(release)` commit, then run:

```sh
python setup/preflight.py
```

It refuses a version that disagrees anywhere, a build that refers to a missing
file, or an ffmpeg licence that has not been decided.

## What happens on the push

1. **Which version.** The workflow reads `APP_VERSION`. If `v<version>` is not
   tagged yet, it builds; a push that leaves the version alone builds nothing.
2. **Three builds, side by side:** macOS on Apple silicon, Windows x86_64, and
   Linux x86_64 (on Ubuntu 22.04, so the AppImage runs on glibc 2.35 and newer).
   Each builds the interface, then the engine with formcut's Rust kernels (an
   engine without them is refused), OpenCV rebuilt without its own FFmpeg,
   formcut's verified ffmpeg from formcut-binaries, the app, and one zip
   (`setup/package_release.py`).
3. **One release.** Only when all three succeed, `v<version>` is tagged and the
   release published with the three zips and notes from `setup/release_notes.py`:
   a download table, how to open each app, and the commits since the last release.

| Zip | Holds |
| --- | --- |
| `formcut-<version>-macos-arm64.zip` | formcut.app |
| `formcut-<version>-windows-x86_64.zip` | a formcut folder: formcut.exe, formcut-engine.exe and ffmpeg beside them |
| `formcut-<version>-linux-x86_64.zip` | the AppImage |

## If a build fails

No tag is made, so nothing half-finished is published. Fix it and push again,
and the same version builds again; or run the workflow by hand (Actions,
release, Run workflow), which also replaces the zips of an existing release.

## Building a zip locally

`setup/build_macos_app` (with `--intel` for Intel Macs) and
`setup/build_linux_app` build the app and write the same zip to `release-dist/`
through `setup/package_release.py`. Intel Macs are not built by the workflow.

## Signing

The apps are unsigned; the release notes say how to open each the first time.
Signing would go in the "build the app" step: an Apple Developer identity for
notarization, a code-signing certificate for Windows.
