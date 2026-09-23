---
name: build-discipline
description: >-
  The rules a change here satisfies: surgical edits, stable DOM, tokens and locale keys, the verification bar, and versioned deliverables.
---

# build discipline

The rules this project is built under. They are here because a change that ignores them passes review and fails later.

## Editing

Hand-made single-region edits to existing files. No scripted rewrites, no patch application, no reformatting a file you are only visiting. Wholesale replacement needs an explicit reason: the file is new, or rebuilding it was the task.

## Interface rules

Stable mounted DOM: patch in place, never rebuild a container, no flash and no layout jump. Every colour, radius, spacing and z value from a token. Inline currentColor SVG icons, no icon dependency. No emoji anywhere. Every user-visible string a locale key in all sixteen locales.

## Verification

A claim that was not run is not a result. Before reporting finished:

- Typecheck and build pass, and the Python compiles.
- The affected flow was driven for real: a browser against the running engine, or a script against the endpoint.
- Numbers are quoted. Not "playback is smooth" but "12.5 s of playback, worst drift 22 ms, under 4x CPU".
- Measurements are taken where the thing measured can happen. Cancelling a finished job, sampling easing at the exact midpoint between two keyframes, or reading a selector document-wide when the surface under test is a dialog all produce confident numbers that mean nothing.
- Anything unverifiable here is named as unverified rather than implied.

## Deliverables

Every turn that changes the repository bumps the version in all eight places (frontend package.json and its lockfile twice, backend main.py, tauri.conf.json, Cargo.toml, Cargo.lock and the readme badge) and hands back a versioned artifact. Commits are scoped to a feature or a fix, never to a version dump, and their messages say what changed, why, and what was measured.

The reasoning behind a change belongs in its commit message; releases and their notes are on the GitHub Releases page. The repository carries the readme, the contributor guide, the wiki source, the project skills and code.

## Naming

Two words never appear anywhere in this repository or its history: the name of the commercial editor this project is an alternative to, and the word used for comparing against it. Provenance comments describing where code came from were removed for the same reason. If a grep would find either, the change is not finished.
