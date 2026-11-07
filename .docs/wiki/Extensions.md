# Extensions

formcut loads extensions under the Form Extension Contract, API 1, the same contract every Form app follows. FormPortal installs them, form.ext makes them and formai.studio lists them; none is bundled with formcut. The API an extension programs against (the document snapshot, the commands, the events) is in [`docs/EXTENSIONS.md`](https://github.com/nodemode-ai/formcut/blob/main/docs/EXTENSIONS.md).

## Using them

- **Extensions menu** in the titlebar: each contributed command, then Extensions Panel, Reload Extensions and Manage in FormPortal.
- **Extensions tab** in the left pane: one row per extension with its version, source (Catalogue, File, Development), permission chips and state (Ready, Needs Permission, Refused with the reason), Open for its panels, Run for its commands, and the folder of a development extension. With nothing installed it points to FormPortal.
- An extension's dock panels open in the same tab, under the list; its dialogs open as formcut dialogs.
- The first time a version runs, formcut asks for the permissions it lists. Allow is remembered for that id, version and permission set; Not Now is asked again next time.

Effect packages (looks, filter chains, shaders) are a separate, older mechanism: data only, imported from the Effects tab.

## How it works

- **Engine.** `backend/app/formext_host.py` is the contract kit's resolver, vendored unchanged: it finds FormPortal's folder, reads `extensions/formcut/enabled.json` (FormPortal) and `dev.json` (form.ext), checks each manifest and serves files safely. `backend/app/extensions.py` mounts `GET /api/extensions` (the list and its `stamp`), `GET /api/extensions/stamp`, `GET /api/extensions/files/{id}/{version}/{path}` (contract headers, 404 for anything outside the folder, a symlink or a type outside the list), and the system file dialogs, `https` fetch and window bridge an extension or agent can ask for. `security.py` lets GET and HEAD on the files route through from this computer with any Origin (a sandboxed frame sends `Origin: null`), since it serves only a package's own files; every other route keeps its guard.
- **Window.** `frontend/src/extensions/host-bridge.ts` is the kit's host, vendored unchanged: the sandboxed frame (`allow-scripts` only), message routing, permission checks, timeouts. `frontend/src/extensions/catalogue.ts` is the document snapshot and the command catalogue over the state engine; `document.apply` runs inside `ProjectEngine.transaction`, so one call is one undo step and a failing op puts the document back. `frontend/src/ui/extensions.ts` builds the menu, the tab, docks, dialogs and consent, polls the stamp every 2 s while the window has focus, and patches only the rows that changed.
- **Agents.** `extensions.list` and `extensions.command` on `POST /api/rpc`, and the MCP tools `formcut_extensions_list` and `formcut_extension_command` (the contract's `<prefix>_` names, since every formcut tool carries the prefix), reach the window through the engine: the window long-polls `GET /api/extensions/agent/next` and answers each request, so consent is asked in the window and an agent can never skip it. With no window open (none has polled in 35 s), `extensions.list` answers from the engine alone and `extensions.command` fails at once with "the formcut window is not open".
- **HTTP RPC only.** `extensions.command` works only through the running engine's HTTP server: `POST /api/rpc` (which the MCP server uses) or the `/api/rpc/ws` websocket, both of which run it off the event loop. `python -m app.cli` (stdin, `--tcp`, `--unix`, `--grpc`) runs the RPC in its own process with no window behind it, so there it always answers "the formcut window is not open".
- **No palette, no step names.** formcut has no command palette, so contributed commands appear as Extensions menu items and as Run chips on each row. Its undo history has no step names, so `document.apply` accepts `label` and does not show it; the call is still one undo step.

## Trying one

1. Copy the contract's `examples/hello` somewhere, set its `product` to `formcut`.
2. Write `extensions/formcut/dev.json` under FormPortal's folder (`FORMPORTAL_ROOT` overrides it) with that folder as `path`.
3. Within 2 s formcut lists it as a Development extension. Open its panel, allow it, and it reads the project.
