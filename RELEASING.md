# Releasing formcut

A release is a tag. Everything else is automatic, and everything that can fail
early is checked before the tag is pushed.

## Before tagging

```sh
python setup/preflight.py
```

It refuses the tag if the version disagrees anywhere, a file the build refers to
is missing, a workflow calls a script that does not exist, the engine does not
import, or the ffmpeg licence has not been recorded. Fix what it names; a
failure here is twenty minutes saved on a runner.

Then, by hand, because they need judgement rather than a check:

1. `BUILD_NOTES.md` in the planning sidecar has a section for this version, with
   the measurement that closed each task.
2. The README's version table has a row for it.
3. The ffmpeg licence recorded in `.docs/wiki/Licences.md` is still the one you
   mean to ship. A GPL build makes the bundle GPL.

## Tagging

```sh
git tag -a v0.73.0 -m "formcut 0.72.0"
git push origin v0.73.0
```

The release workflow then, on macOS for both architectures, on Linux and on
Windows: fetches ffmpeg into the bundle, freezes the engine with
`backend/freeze.py`, builds the interface, and runs `tauri build`. Artefacts are
attached to a **draft** release.

## Before publishing the draft

The workflow has never been run end to end, so treat the first tag as a shakedown.

1. Open each artefact once on its own platform. A bundle that builds and does not
   launch is the usual first failure, and signing is the usual cause.
2. Check the engine starts inside the bundle rather than from a stray Python on
   the machine: the diagnostics panel reports the version and where it is running.
3. Confirm the macOS build is notarized and the Windows installer signed;
   without these the first launch is blocked by the operating system, not by us.

## If the build fails

- **Missing `binaries/formcut-engine`** — `freeze.py` did not run or wrote elsewhere.
- **ffmpeg not found at runtime** — the fetch step was skipped, or the binaries
  landed outside `src-tauri/binaries`.
- **Notarization rejected** — usually an unsigned nested binary; the engine and
  ffmpeg both need signing, not only the app.
