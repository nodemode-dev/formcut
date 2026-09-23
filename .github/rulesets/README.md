# Protecting main

`main.json` is a ruleset for the default branch. Import it once: Settings, Rules, Rulesets, New ruleset, Import a ruleset, then choose this file.

It makes every change to main arrive by pull request, with:

- all seven checks passing on an up-to-date branch: `interface` and `engine` on Ubuntu, macOS and Windows, and `desktop shell`
- an approving review from the code owner (`.github/CODEOWNERS`), given after the last push, with every review thread resolved
- no force-pushes and no deleting main

Repository admins can bypass it, so the maintainer can still push a release straight to main. After importing, check that the bypass list shows Repository admin, and that the required checks match the job names in `.github/workflows/checks.yml`; if a job is renamed there, rename it here.
