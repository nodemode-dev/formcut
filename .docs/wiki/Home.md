# formcut wiki

Start with the [README](../README.md) for what the app does and how to run it.
This wiki holds the subsystem map and the contracts between parts.

- [Architecture](Architecture.md): the engine, the shared renderer, playback and
  where state lives
- [Creator workflow](Creator-workflow.md): the editing surface, effects,
  captions, speech and cutout
- [Automation](Automation.md): the JSON-RPC surface for scripted editing
- [Packaging](Packaging.md): desktop shell, portable build and environment

Development records live in the planning sidecar rather than in this
repository: the phased plan, the per-version build notes and the reasoning logs
for every area. `.docs/` carries these pages, the asset and dependency licences
and the mobile layout notes. These pages are the editable source for the GitHub
wiki; a push to main that touches them publishes the wiki through
`.github/workflows/publish-wiki.yml`, `_Sidebar.md` included, which is the
navigation shown beside every wiki page.
When a document here disagrees with the running code, the code wins and the
document is corrected in the same change.
