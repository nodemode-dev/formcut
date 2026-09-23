# Contributing to formcut

Thank you for helping. formcut aims to be a free, local-first video editor that
does everything CapCut does and more, and it gets there through real use and real
contributions.

## Where to start

- **Use it and report what goes wrong.** A clear bug report, with steps, the version
  and your platform, is one of the most useful things you can give.
- **Look at the open issues.** Comment on one before starting larger work, so nobody
  builds the same thing twice.
- **Translations** are welcome: formcut ships in twelve languages, and every new
  string needs all twelve.

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
- Interface text goes through the translation files, in all twelve languages.
- ffmpeg stays LGPL. Nothing that would make formcut's builds GPL (such as libx264)
  can be bundled; formcut's own ffmpeg builds live in the formcut-binaries
  repository.

## How changes land

Only the maintainer pushes to `main`. Everyone else forks the repository and opens a pull request into `main`, which the pull request template walks through. A pull request merges when all seven checks pass on an up-to-date branch and the maintainer has approved it after its last push. Other branches run no checks until they are proposed for `main`.

## Releases

A release is a version: bumping it on `main` makes the release workflow build macOS,
Windows and Linux and publish them. See [RELEASING.md](RELEASING.md).

## Licensing

formcut is licensed under the Apache License 2.0. By contributing, you agree that
your contribution is licensed under the same terms. Only add code you have the right
to contribute, and name any third-party code and its licence in the pull request.

## Conduct

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md). Security
problems go through [SECURITY.md](SECURITY.md), never a public issue.
