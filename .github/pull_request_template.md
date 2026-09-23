## What this changes

<!-- One change per pull request: what it does and why. Link the issue it closes. -->

## Checklist

Everything here is in [CONTRIBUTING.md](../CONTRIBUTING.md).

- [ ] One change, with tests for what it adds or fixes
- [ ] The checks pass locally: `ruff check backend/app mcp setup tests`, `ruff format --check backend/app mcp setup tests`, `python -m pytest tests -q`, `(cd frontend && npm run build)`
- [ ] Generated files are current: `python setup/skill_maps.py --check` (run it without `--check` to update)
- [ ] Commit subjects follow the history: `feat(scope): ...`, `fix(scope): ...`, `docs(...)`, `test(...)`
- [ ] New interface text is in the translation files, in all twelve languages
- [ ] Nothing makes formcut's builds GPL (ffmpeg stays LGPL)
- [ ] I agree my contribution is licensed under Apache-2.0 and follows the Code of Conduct
