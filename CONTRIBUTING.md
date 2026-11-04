# Contributing to formcut

Thank you for helping. formcut aims to be a free, local-first video editor that
does everything CapCut does and more, and it gets there through real use and real
contributions.

## Where to start

- **Use it and report what goes wrong.** A clear bug report, with steps, the version
  and your platform, is one of the most useful things you can give.
- **Look at the open issues.** Comment on one before starting larger work, so nobody
  builds the same thing twice.
- **Translations** are welcome: formcut ships in sixteen languages, and every
  new string needs all sixteen.
- **Caption looks** need no code. Style a caption track, choose **Share this look**
  in the Captions panel, and list the zip it saves in the
  [community registry](.docs/registry/README.md) with `setup/registry_entry.py`:
  anyone can then install it from the effects browser's Community packages.

## Setting up

Clone the repository and run `./formcut` (or `formcut.bat` on Windows). It installs
what the engine and the interface need and starts both; the README's Quick Start has
the details and the requirements.

The code lives in:

| Folder | What is there |
| --- | --- |
| `backend/app` | the engine (Python, FastAPI): media, rendering, export, models |
| `backend/native` | the Rust kernels the renderer calls |
| `frontend/src` | the interface (TypeScript, Vite) |
| `src-tauri` | the desktop shell (Rust, Tauri) |
| `mcp` | the MCP server |
| `setup` | build, packaging and release scripts |
| `tests` | the test suite |
| `.docs/wiki` | the wiki's source, published on push |

## Before you open a pull request

Run the same checks CI runs:

```sh
ruff check backend/app mcp setup tests
ruff format --check backend/app mcp setup tests
python -m pytest tests -q
(cd frontend && npm run build)
```

- Keep each pull request to one change, with tests for what it adds or fixes.
- Write commit subjects the way the history does: `feat(export): ...`,
  `fix(timeline): ...`, `test(...)`, `docs(...)`.
- Interface text goes through the translation files, in all sixteen languages:
  twelve in `frontend/src/i18n`, and Arabic, Persian, Hebrew and Croatian in
  `frontend/public/locales` (see the Translation page of the wiki).
- ffmpeg stays LGPL. Nothing that would make formcut's builds GPL (such as libx264)
  can be bundled; formcut's own ffmpeg builds live in the formcut-binaries
  repository.

## How changes land

Only the maintainer pushes to `main`. Everyone else forks the repository and opens a pull request into `main`, which the pull request template walks through. A pull request merges when all seven checks pass on an up-to-date branch and the maintainer has approved it after its last push. Other branches run no checks until they are proposed for `main`.

## Releases

A release is a version, and only the maintainer makes one: after the version is bumped on
`main`, the maintainer runs the release workflow by hand, which builds every platform and
publishes them together. No push starts a release. See [RELEASING.md](RELEASING.md).

## Licensing

formcut is licensed under the Apache License 2.0. By contributing, you agree that
your contribution is licensed under the same terms. Only add code you have the right
to contribute, and name any third-party code and its licence in the pull request.

## Patents and other people's IP

Some features are deliberately not built, or were taken out, because they come too close to someone else's patent, trademark, copyright or design. The maintainers hold that line with counsel; contributors do not decide it, and nobody here redesigns a feature on their own reading of a patent. This is engineering diligence, not legal advice.

### Features this project will not implement

- Cutting footage from the transcript. The transcript marks and the timeline cuts: the transcript panel never cuts, copies or pastes footage; a range's edges come from the speech in the audio, never from caption or word times; a transcript row or word selection never selects footage; no word-level selection snapped to word boundaries; no sharing a transcript selection as a clip; no cutting by deleting words from the transcript text.
- A filler-word cut that works as "select filler text, then cut". The finder stays automatic: it finds ranges for review and cuts them as a batch.

A pull request that adds one of these, under any name, through any dependency, plug-in, model, template, agent tool or plain code, is closed with a link to this section. Lifting a decline needs the maintainers' written decision after a review, recorded here first.

### Rules for every contribution

- Patents: do not add a feature, or a dependency that provides one, that reproduces a method you know to be patented. If you are unsure, open an issue that describes what the feature does, not which patent it resembles. Patent numbers stay out of code, commits, comments, logs and changelogs.
- Trademarks: other vendors' product and feature names appear only to name a file format or compatibility ("opens <format> files", "for use with"). No command, menu, panel, tool, preset, template, theme or agent tool takes another product's feature name, and no text says "like X" or "the way X does it". Describe what the feature does.
- Copyright: never copy another product's help, tooltip, dialog or documentation text (link to it instead); never trace or import vendor icons; never bundle vendor templates, themes, presets, brushes, swatches, LUTs, materials, sample files, sound libraries, stock media or fonts; colour-book names only when reading a person's file. Compatibility layers carry names and signatures only. Test fixtures come from this repository's own scripts.
- Licences: every new dependency, binary, model, font, profile or data file gets a row in `NOTICE` before it is used. GPL stays outside the distributed bundle, AGPL nowhere, LGPL dynamically linked and replaceable, MPL files unedited. CC BY credited, CC BY-SA only unmodified, CC NC and ND never. Models with gated or non-commercial terms are optional downloads, never bundled.
- Licence conditions: The H.264 software codec is downloaded separately from its publisher under its own terms, is never bundled, shows its attribution in the app and can be turned off; keep all three.

## Conduct

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md). Security
problems go through [SECURITY.md](SECURITY.md), never a public issue.
