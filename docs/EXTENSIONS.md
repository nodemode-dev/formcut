# Extensions in formcut

formcut hosts extensions under the Form Extension Contract, API 1. An extension is a folder (or a `.formpkg` that FormPortal unpacks) with a `manifest.json` whose `product` is `formcut`; formcut loads its page in a sandboxed frame and answers its requests over `postMessage`. This page is what is particular to formcut: what the document looks like, which commands an extension may run, which events it hears, and where it appears.

## Where extensions appear

- **Extensions menu**, in the titlebar after View: one item per contributed command (`Name: Title`), then Extensions Panel, Reload Extensions and Manage in FormPortal (`formai://extensions?product=formcut`).
- **Extensions panel**: the Extensions tab of the left pane, beside Media, Effects and the others. One row per extension with its name, version, source (Catalogue, File or Development), permission chips and state (Ready, Needs Permission, or Refused with the reason), Open buttons for its panels, and the folder path for a development extension.
- **Dock panels** (`location: "dock"`) open inside the Extensions tab, under the list, titled `Extension Name: Panel Title`. Several can stay open; a chip row switches between them and each has a close button.
- **Dialog panels** (`location: "dialog"`) open as a formcut modal, titled the same way.
- **Agents**: the MCP tools `formcut_extensions_list` and `formcut_extension_command` (every formcut MCP tool carries the `formcut_` prefix, so the contract's names take it too), and the JSON-RPC methods `extensions.list` and `extensions.command`. A command an agent runs asks for consent in the window the same way a click does.

formcut has no command palette, so contributed commands are listed in the Extensions menu and in the Extensions panel (a Run chip per command).

### Agents reach extensions through the engine's HTTP RPC only

Extension pages and their consent dialog live in the window, so `extensions.list` and `extensions.command` are handed from the engine to the open window (the window long-polls `GET /api/extensions/agent/next` and posts each answer). That works only for requests that reach the running engine over HTTP: `POST /api/rpc` (which the MCP tools use) and the `/api/rpc/ws` websocket.

- `python -m app.cli` and its other framings (`--tcp`, `--unix`, `--grpc`) run the RPC in their own process with no window behind it: `extensions.command` fails at once with "the formcut window is not open", and `extensions.list` answers from the folders alone, without permission state.
- With the engine running but no window open, the same happens: no window has polled in the last 35 s, so the request fails at once instead of waiting.
- `extensions.command` waits up to 150 s for the window's answer, the consent dialog included; the MCP tool allows 180 s.

## host.hello

```json
{ "product": "formcut", "app": "formcut", "appVersion": "2.14.0", "api": "1",
  "extension": { "id": "beat-markers", "version": "0.1.0", "source": "development" },
  "permissions": ["document"], "theme": { "mode": "dark", "tokens": { "--bg": "#0a0a0a", "...": "..." } }, "locale": "en" }
```

Theme tokens sent: `--bg --panel --text --muted --accent --border --radius`, plus `--accent-text --danger --float --control --font-ui --font-mono` (the active formcut appearance profile and accent, resolved to plain values). `ext.theme` is sent again when the person changes the profile or the accent.

## document.read

`document.read` takes `{ what? }`. `what` is one of:

| what | returns |
|---|---|
| `project` (default) | `project`, `timeline` (the active one, with tracks, clips and markers), `selection`, `media` |
| `timeline` | `timeline` only |
| `selection` | `selection` and the selected clips in full summary |
| `media` | `media` only (the library) |
| `markers` | `markers` of the active timeline |
| `full` | `state`, the whole formcut project document as the editor holds it (every clip field), plus `media` |

Times are seconds on the timeline. Track index 0 is the top track. A clip's `sourceIn` is where it starts in its media, in source seconds. Example, read from the formcut window built in this round after a new 9:16 project had one library item (`tone.wav`), one title and one marker added through `document.apply` (ids shortened here):

```json
{
  "product": "formcut",
  "what": "project",
  "project": { "id": null, "title": "Untitled project", "revision": null, "saved": false, "width": 1080, "height": 1920, "fps": 30, "aspect": "9:16", "duration": 8, "playhead": 0, "playing": false },
  "timeline": {
    "index": 0, "count": 1, "id": "tl1", "name": "Timeline 1", "width": 1080, "height": 1920, "fps": 30,
    "tracks": [
      { "index": 0, "id": "t1", "name": "Titles", "locked": false, "hidden": false, "muted": false, "magnetic": false,
        "clips": [ { "id": "a4c77736", "kind": "text", "label": "Opening title", "start": 1, "duration": 3, "mediaId": null, "sourceIn": 0, "speed": 1, "muted": false, "volume": 1, "text": "Opening title" } ] },
      { "index": 1, "id": "t2", "name": "Overlay", "locked": false, "hidden": false, "muted": false, "magnetic": false, "clips": [] },
      { "index": 2, "id": "t3", "name": "Video", "locked": false, "hidden": false, "muted": false, "magnetic": false, "clips": [] },
      { "index": 3, "id": "t4", "name": "Audio", "locked": false, "hidden": false, "muted": false, "magnetic": false,
        "clips": [ { "id": "4677a6c2", "kind": "audio", "label": "tone.wav", "start": 0, "duration": 8, "mediaId": "4b855bd8", "sourceIn": 0, "speed": 1, "muted": false, "volume": 1 } ] }
    ],
    "markers": [ { "id": "699bdf51", "t": 2.5, "note": "drop", "colour": null } ]
  },
  "selection": { "clipId": null, "clipIds": [], "range": null },
  "media": [ { "id": "4b855bd8", "name": "tone.wav", "kind": "audio", "duration": 8, "width": 0, "height": 0, "fps": 0 } ]
}
```

A text clip also carries `text` (its words). The exact ids and track names depend on the project; read them, never assume them.

## document.apply and app.run

`document.apply` takes `{ label, ops: [{ command, args }] }` and runs every op through formcut's own editor commands, the ones its timeline, menus and keys use, as **one undo step**: one Undo takes the whole call back. If any op fails, nothing is applied (the document is put back as it was) and the call fails with -32004 naming the op. The result is `{ applied, results }`, one result per op (for example the id of the clip or marker it made). formcut's history has no step names, so `label` is not shown in the app.

`app.run` takes `{ command, args }` and runs one command from the same catalogue (an edit runs as one undo step), plus the view and analysis commands below that do not change the document. `app.commands` returns the whole catalogue as `[{ id, title, args, kind }]`, where `kind` is `edit`, `view` or `analysis`; only `edit` commands are accepted by `document.apply`.

Edit commands (document.apply and app.run):

| command | args | result |
|---|---|---|
| `marker.add` | `{ t, note?, colour? }` | `{ markerId }` |
| `marker.update` | `{ id, t?, note?, colour? }` | `{}` |
| `marker.remove` | `{ id }` | `{}` |
| `clip.add` | `{ trackIndex, mediaId, start, duration?, sourceIn?, label? }` (a library item onto a track) | `{ clipId }` |
| `text.add` | `{ trackIndex, start, duration, text }` (a title) | `{ clipId }` |
| `captions.add` | `{ trackIndex, cues: [{ start, end, text }] }` | `{ clipIds }` |
| `clip.remove` | `{ clipId }` | `{}` |
| `clips.remove` | `{ clipIds }` | `{}` |
| `clip.split` | `{ clipId, time }` | `{ clipId }` (the tail) |
| `clips.split` | `{ clipIds, time }` | `{ clipIds }` (the tails) |
| `clip.move` | `{ clipId, start, trackIndex? }` | `{}` |
| `clips.move` | `{ clipIds, deltaStart, deltaTrack? }` | `{}` |
| `clip.trim` | `{ clipId, start, duration }` | `{}` |
| `clip.mute` | `{ clipId, muted }` | `{}` |
| `clip.transition` | `{ clipId, type, duration }`, or `{ clipId, type: null }` to remove; types: `crossfade dissolve dip wipe-left wipe-right wipe-up wipe-down slide-left slide-right push-up push-down cover-left cover-up zoom iris clock-wipe blinds diagonal-wipe pixel-dissolve blur-fade spin diamond barn-door` | `{}` |
| `clip.transform` | `{ clipId, patch: { scale?, posX?, posY?, rotation?, opacity? } }` | `{}` |
| `clip.colour` | `{ clipId, colour: { exposure?, brightness?, contrast?, highlights?, shadows?, whites?, blacks?, saturation?, temperature?, tint?, sharpen?, fade?, vignette? } }`, or `colour: null` to reset | `{}` |
| `clip.text` | `{ clipId, patch: { content?, size?, color?, bold?, align? } }` (text clips) | `{}` |
| `track.add` | `{ name? }` | `{ trackIndex }` |
| `track.update` | `{ index, patch: { name?, locked?, hidden?, muted?, magnetic? } }` | `{}` |
| `timeline.cut-range` | `{ start, end }` (removes the span on every track and closes the gap) | `{}` |
| `project.rename` | `{ title }` | `{}` |

View commands (app.run only; no undo step): `transport.seek { time }`, `transport.play {}`, `transport.pause {}`, `clip.select { clipId }` (null clears), `clips.select { clipIds }`, `range.set { start, end }`, `range.clear {}`.

Analysis commands (app.run only; they read media through the engine and change nothing): `media.beats { mediaId, sensitivity? }` returns `{ beats, count, bpm, bar, first_beat, final_hit }` (`beats` are onset times in source seconds), `media.scenes { mediaId, sensitivity? }` returns the scene cuts, `media.ducking { mediaId, depth? }` returns a ducking envelope.

A command or args formcut does not know fail with -32602; a locked track, a missing clip or anything else formcut refuses fail with -32004 and formcut's reason.

## Events (`ext.event`)

| name | data | when |
|---|---|---|
| `document.changed` | `{ changed: "clips" \| "timeline" \| "project" }` | after any edit, undo or redo, at most once per frame |
| `selection.changed` | `{ clipId, clipIds }` | the clip selection changes |
| `transport.changed` | `{ playing, playhead }` | play, pause or a seek (not every frame of playback) |

## Files and network

- `files.open` (`files-read`): available. In the desktop app it opens the system's own file dialog through the engine; in a browser, the browser's file picker. At most 200 MB in total.
- `files.save` (`files-write`): available. The system's save dialog in the desktop app. Where the engine has no save dialog (a browser, or a computer without one), formcut shows its own Save to Downloads dialog to confirm the name and the engine saves the file into the Downloads folder of the account it runs as, as `name (2).ext` when the name is taken; Cancel answers -32002.
- `net.fetch` (`network`): available, through the engine, `https://` only, at most 50 MB, never to this computer or the local network.
- `storage.get` and `storage.set`: available, 256 KB per extension.

## Running an extension

- **From a folder (development).** form.ext's Run in App writes `extensions/formcut/dev.json` under FormPortal's root (`FORMPORTAL_ROOT`, else `~/Library/Application Support/studio.formai.portal` on macOS, `%LOCALAPPDATA%\FormPortal` on Windows, `$XDG_DATA_HOME/formportal` or `~/.local/share/formportal` elsewhere). By hand:

  ```json
  { "format": "formext-dev-extensions", "format_version": 1, "product": "formcut",
    "extensions": [ { "id": "beat-markers", "path": "/home/me/beat-markers", "added": "2026-11-07T10:00:00Z" } ] }
  ```

  formcut notices the file within 2 s while its window has focus, or at once on Extensions > Reload Extensions. A development extension shows its folder in the panel; after editing its files, Reload Extensions loads them again.
- **Installed.** FormPortal installs a `.formpkg`, unpacks it and writes `extensions/formcut/enabled.json`; formcut picks it up the same way, with the source Catalogue (or File for a sideloaded package).
- The first time an extension version runs, formcut asks for its permissions (Allow or Not Now). The answer is kept per id, version and permission set.

## Limits

Refused with the reason in the panel: a manifest that is not valid or not a formai package, an id or product that does not match, `api` other than `"1"`, `native: true`, an `entry.ui` outside the package, and `minimum_app` newer than this formcut. Pages run with `sandbox="allow-scripts"` and the contract's content security policy (no network from the page itself, no frames, no forms); everything goes through the methods above.
