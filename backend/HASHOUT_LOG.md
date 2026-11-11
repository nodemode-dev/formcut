# HASHOUT_LOG · engine

Reasoning behind engine changes, newest first.

## 2.15.4 · .cube files with an input range line import

- **What was wrong.** `assets.parse_cube` counted any three-token line as a table row, so a `LUT_3D_INPUT_RANGE 0.0 1.0` line, which Resolve writes, put the row count off by one and the upload was refused as "LUT size or color domain is invalid". A bare `LUT_3D_SIZE` line raised `IndexError`, which `upload_lut` does not map, so it was a 500.
- **The fix.** `LUT_3D_INPUT_RANGE lo hi` sets the domain to `lo` and `hi` on all three channels; `LUT_3D_SIZE` without exactly one number is a `ValueError`; a `LUT_1D...` keyword still says "Only 3D .cube LUTs are supported"; any other keyword (a letter-first token with an underscore) is skipped rather than read as a row.
- **Checked.** A throwaway script outside the repo: a 2-point cube parses plain, with `TITLE` and `LUT_3D_INPUT_RANGE 0.0 1.0`, and with an unknown `LUT_IN_VIDEO_RANGE` line; a bare `LUT_3D_SIZE` and a 1D cube are refused with `ValueError`. ruff clean.

## 2.15.4 · malformed JSON-RPC answers with a JSON-RPC error

- **What was wrong.** `automation.rpc` passed `params` to the dispatcher whatever its type, so `"params": [1]` raised `AttributeError` at `params.get`, which `rpc` does not catch: HTTP 500, which the MCP tools report as "non-JSON reply". `timeline.cuts` and `timeline.frames` built their source map with `next(iter(MEDIA_DIR.glob(...)))`, and a clip whose media file is gone raised `StopIteration`, which a coroutine turns into `RuntimeError`. On `/api/rpc/ws` any of these, or a frame that is not JSON, ended the socket.
- **The fix.** `params` that is not an object answers -32602 "params must be an object". The two source maps use `next(..., None)` and raise `ValueError("Media file is missing")`, which `rpc` already answers as -32602. The websocket answers a frame that does not parse as JSON (or is binary) with -32700 and keeps the connection.
- **Checked.** A throwaway script outside the repo: the report's `session.hello` with `[1]` answers HTTP 200 with the -32602 error; on the websocket, text that is not JSON and a binary frame each get -32700 and the next request on the same socket is answered. The missing-media path was not run. ruff clean. `tests/test_agent_connection.py`: 7 passed, 1 failed (`test_an_agent_drives_the_running_engine` starts the real engine, which needs uvicorn and OpenCV, not installed here).

## 2.15.4 · a closed terminal leaves no zombie, and an exited shell closes its pane

- **What was wrong.** `terminal.Session.close` sent SIGHUP and at once called `waitpid(pid, WNOHANG)`; the shell had not exited yet, so it was never reaped and each closed pane left a zombie until the engine stopped. When the shell exited by itself (`exit`), the reader's `None` only ended the sender, the socket stayed open, and the next keystroke's `os.write` raised `OSError` (EIO) out of the handler.
- **The fix.** `close` reaps the shell with a blocking `waitpid` on a daemon thread. The sender closes the socket when the reader ends (errors from a socket already gone are ignored), and a write that fails with `OSError` ends the loop, so the `finally` cleans up as on a disconnect.
- **Checked.** A throwaway script outside the repo with `/bin/sh` through the real route: five panes opened and closed left no `Z` child of the process, and typing `exit` closed the socket with 1000. ruff clean. Windows path (pipe-driven cmd.exe) not run.

## 2.15.4 · formcut.bat mcp and agents pass on python's exit code

- **What was wrong.** In `formcut.bat` (the launcher at the top of the checkout; there is no log beside it, so it is noted here with the engine it starts) the `mcp` and `agents` branches ended with `exit /b %ERRORLEVEL%` inside a parenthesised `if` block. cmd expands `%ERRORLEVEL%` when it parses the block, before python runs, so the script exited with the earlier level (normally 0) and `formcut.bat agents sync --check` never failed on drift.
- **The fix.** Both lines are `exit /b`, which leaves the current errorlevel, the one python just set, as the exit code. CRLF endings kept (checked with `file` and a count of CR lines before and after).
- **Checked.** Reasoned from cmd's documented block parsing and `exit /b` behaviour. Not run on Windows.

## 2.15.4 · an asset that is not on this computer is left out, not fatal

- **What was wrong.** A project opened from an .fmc made elsewhere (only media travels in one) can name a LUT, shader or font id this data folder lacks. `assets.asset_path` raises `ValueError("Asset is unavailable")` for it, before `project_packages.gather_assets` reached its `if not path.is_file(): continue`, so package export failed with 500, "Save as template" (`template_assets.gather`) did the same, and a save with a sync folder answered 409 although the project had been stored, because `store.save_project` suppressed only `OSError` around `sync_after_save`.
- **The fix.** Both gather functions skip an id `asset_path` refuses, which is what the dead `is_file` check meant to do, and `save_project` suppresses `ValueError` as well as `OSError` around the sync, as its comment says a failed sync must not fail the save.
- **Checked.** A throwaway script outside the repo: a clip with a random lutId and fontId gives an empty asset set from both gather functions instead of raising. The sync path was not run. ruff clean.

## 2.15.4 · the fast-path check runs when an export names a rate

- **What was wrong.** `held_to_frame_path` (R25) found the middle frame's instant as `index / float(out_rate)`, but `out_rate` is a ratio string whenever the export names a rate (`"24000/1001"`, and `"30/1"` for a whole rate too). `float` raised, the handler logged "the check failed; keeping the export", and the comparison against the frame path never ran for those exports.
- **The fix.** The rate is read with `Fraction`, as the bitrate estimate a few lines further on already does. The instant is the same one the code meant (`k / out_rate`, the rate ffmpeg's `-r` writes); only the parse changed. The reviewer's suggestion of `k / project fps` was not taken: with `-r 24000/1001` on a 24 fps graph the two differ by about 30 ms at a minute's middle frame, and which one matches the file's frame k is not settled by reading alone.
- **Checked.** `float(Fraction(r))` for `24000/1001`, `30/1` and `30`; `float("30/1")` raises as reported. Not run as an export (OpenCV is not installed here). ruff clean.

## 2.15.4 · a preset with a non-Latin name exports

- **What was wrong.** `presets.export_preset` put the preset's name raw into `Content-Disposition`. `_clean_name` keeps any letters, so a preset named "Заголовок" or "見出し" made Starlette's latin-1 header encoding raise and the download answered 500.
- **The fix.** The header carries `filename*=UTF-8''<percent-encoded name>` (RFC 6266), and the plain `filename` is the name when it is ASCII, `preset.fcpreset` otherwise.
- **Checked.** A throwaway script outside the repo: "Заголовок" exports 200 with `filename="preset.fcpreset"; filename*=UTF-8''%D0%97...`, and "Title one" still gives `Title_one.fcpreset`. ruff clean.

## 2.15.4 · a malformed .fc is refused before anything is ingested

- **What was wrong.** The 2.15.3 hardening covered assets and the media index only. In `project_packages.unpack` a manifest that is a JSON array raised `AttributeError` at `manifest.get`; a document with `"timelines": [5]` or a clip with `"textStyle": "x"` was only validated after its media had been ingested, and the `AttributeError` from `clip_values` escaped `import_package` as a 500; a clip with `"device": 3` raised in the screen loop. `POST /api/project-files/open` called `unpack` with no mapping at all, so even "Not a formcut project package" was a 500 there.
- **The fix.** A manifest that is not an object is "Not a formcut project package". The document is validated right after it is read, before any asset or media is restored. The device-screen loop reads `device` and `screens` only when they are objects. `import_package` and `open_project_file` map `ValueError`, `KeyError`, `TypeError` and `AttributeError` to 422.
- **Checked.** A throwaway script outside the repo posted four crafted packages to both routes with `ingest_path` counted: the array manifest, `timelines [5]` and `textStyle "x"` answer 422 on both with nothing ingested; a text clip carrying `device: 3` imports (the field is ignored). `tests/test_package_import.py` and `test_project_files.py` with a cv2 stub plugin: 16 passed, 2 failed in tests that call OpenCV's `cvtColor` (not installed here). ruff clean.

## 2.15.4 · a credentials file restored from its backup stays private

- **What was wrong.** `durable.read_json` restores a missing or damaged file from `<name>.bak` with `write_json(..., keep_backup=False)` and no `private`, so `providers.json` or `cloud.json` (written 0600, holding API keys and OAuth tokens) came back with the umask default, usually 0644.
- **The fix.** The restoring write is private when the backup itself grants nothing to group or others (`st_mode & 0o077 == 0`); a private file's backup is written 0600 by `write_json`, so the restored file keeps that mode. Callers did not change.
- **Checked.** A throwaway script outside the repo under umask 022: a file written private, then deleted, is restored 0600; one written normally is restored 0644. `tests/test_durable.py`: 4 passed. ruff clean.

## 2.15.4 · the exported mix follows keyed volume

- **What was wrong.** `audio_render.mix_audio` built its own envelope from the fades times the static `volume`, so a clip's `volumeKeys` (accepted by `clip.update`, listed in the RPC capabilities, checked by `validation.py`) never reached the export. `clip_envelope`, the curve `render_api.clip_audio`'s docstring says the export applies, was never called by the export.
- **The fix.** `mix_audio` multiplies by `clip_envelope(clip, count)`: the same fades, times `volume_at`, which is the static volume when there are no keys, clamped to 0 to 4 as before.
- **Checked.** A throwaway script outside the repo with a constant-one source: keys 0 at 0 s and 1 at 1 s give 0.0, 0.5, 1.0 and 1.0 at 0, 0.5, 1 and 1.5 s; a static volume of 9 still mixes at 4. No existing test covers `mix_audio`. ruff clean. The interface's live mix still plays the static volume (a frontend matter).

## 2.15.4 · the heavy RPC methods run off the event loop

- **What was wrong.** `http_rpc` and `websocket_rpc` are `async` and called the synchronous dispatcher on the loop thread for every method but `extensions.*`. `media.qc` (ffmpeg over a whole render), `media.import` (copies and probes a file), `media.scenes`, `media.music`, `media.beats`, `media.ducking` and `speech.range` could hold the loop for minutes, so preview frames, job polling and the extension long-poll all waited and the MCP client's own timeout fired.
- **The fix.** `OFF_LOOP` names the prefixes sent to `run_in_threadpool`: `extensions.` as before, plus those seven methods. They touch no project document, and each calls the same functions the synchronous HTTP routes already run on worker threads. Every other method, the project edits included, keeps running on the loop, so their serial order is unchanged.
- **Checked.** A throwaway script outside the repo with `dispatch` replaced by a 1 s sleep: a `GET` sent while `media.qc` ran answered after 0.10 s (worker thread), and after 1.00 s while `project.get` ran (loop thread, unchanged). ruff clean.

## 2.15.4 · the frame check's keep-alive push keeps a clip's other keyframes

- **What was wrong.** When no source shift or speed-up frees a clip of repeated pictures, `cadence.solve_clip` answers with a scale push, and `timeline.frames` with `fix` applies it as `clip.update` with `{"keyframes": push}`, replacing the whole list. A hold carrying posX, opacity or effect keys lost all of them.
- **The fix.** The change is the clip's existing keyframes plus the two push keys, sorted by time. `solve_clip` only reaches the push when the clip has no scale key (`pushed`), so nothing the push sets is duplicated; keys of other properties at the same time are read per property, as `focus_motion.merged_keyframes` already relies on.
- **Not changed.** The push still compounds 0.1 % per output frame, so a long hold ends far above 100 % (about 135 % at 10 s, 605 % at 60 s). Capping it would let the last frames of a long hold repeat again, so the limit is left to the owner.
- **Checked.** A throwaway script outside the repo: a 2 s hold with two posX keys comes back with both posX keys and the scale keys 100 and 106.18. ruff clean.

## 2.15.4 · timeline.cut-range keeps a sped-up clip's tail on the right footage

- **What was wrong.** The RPC's `timeline.cut-range` in `app/automation.py` moved a kept tail's `sourceIn` on by timeline seconds (`sourceIn + (end - start)`), where `clip.split` uses `source_time`. At 2x the tail of a 2 to 4 s cut restarted at source 4 s instead of 8 s, replaying the words the remove-speech workflow meant to take out. Its keyframes and speed curve also kept their old clip-local times.
- **The fix.** For the tail of a clip that straddles the range, and for a clip that starts inside it, the offset into the clip is `end - clip start`: `sourceIn` becomes `source_time(clip, offset)`, keyframes move back by the offset, and a speed curve is rebased the way `clip.split` does it (a point at 0 with the speed there, then the later points shifted). The interface's own copy of the command is fixed separately in the frontend.
- **Checked.** A throwaway script outside the repo: a 2x clip cut over 2 to 4 s leaves a tail at sourceIn 8 with its key at t 0; a 2x clip starting inside the range at 3 s with sourceIn 1 becomes sourceIn 3; a 1 to 3 ramp over 6 s cut over 1 to 3 gives sourceIn 4.5 and the curve [0: 2, 3: 3]. No existing test covers cut-range. ruff clean.

## 2.15.4 · the speech runtime installs where .env puts the data folder

- **What was wrong.** `./formcut` and `formcut.bat` run `setup_local_ai` before `formcut_boot`, the only step that loads `.env`. `backend/setup_local_ai.py` read `app.paths.DATA_DIR` at import, so with `FORMCUT_DATA_DIR` set in `.env` (as `example.env` documents) kokoro-onnx went into the default data folder, the engine looked in the configured one, and local voices stayed unavailable while every launch said "already installed".
- **The fix.** `setup_local_ai.main` reads `FORMCUT_DATA_DIR` from the checkout's `.env` (the same `key=value` reading `setup/mcp_stdio.py` does, quotes stripped) before importing `DATA_DIR`. A value in `.env` wins, as it does for the engine, which both boot scripts start after loading `.env` over the environment. Neither launcher changed.
- **Checked.** A throwaway copy of the script in a scratch tree with a `.env` naming `/tmp/fixA-data` (venv creation and pip stubbed) chose `/tmp/fixA-data/ai-runtime`. ruff reports only the `subprocess.run` without `check` that was already there.

## 2.15.4 · preview read-ahead fills the frames the frame route serves

- **What was wrong.** `ReadAhead` stored its frames under tag `""`, but the only reader, `GET /sessions/{id}/frame`, asks for tag `"orig"`, so every read-ahead frame was waste that evicted still frames from the shared 240-frame cache and held the session lock. Its render function also closed over the renderer the session was created with, so after `retarget_session` closed that renderer and installed a new one, read-ahead kept drawing the old document through a closed renderer.
- **The fix.** `ReadAhead` takes a `tag` and uses it for both `get` and `put`; the session passes `"orig"`. `render_locked` looks up the session's current renderer under the session lock and draws from the original with `allow_proxy = False`, exactly as the frame route does, so a read-ahead frame is the frame the route would have drawn (no display roll-off, which the route does not apply either).
- **Checked.** A throwaway script outside the repo with a fake renderer: after a frame at 0 s the read-ahead frames are cached, a request at 0.5 s is a hit (it was a miss), and after a retarget the closed renderer draws nothing more while the new one fills the cache. Not run with the real renderer (OpenCV is not installed here). ruff clean.

## 2.15.4 · without ffprobe, a video keeps its frame rate

- **What broke.** When ffprobe is missing or fails, `tools.probe` reads ffmpeg's own report through `_from_ffmpeg`, which wrote `avg_frame_rate` as `f"{float}/1"`, for example `"30.0/1"` or `"29.97/1"`. `Fraction` and `int` both refuse a decimal numerator, so the media record got fps 0 and `VideoSource` fell back to 30 fps, decoding a 24, 25 or 60 fps clip with the wrong frame-to-time mapping.
- **The fix.** The rate is read as a `Fraction` and written as an integer ratio. A rate that is within 0.01 of an n x 1000/1001 rate becomes that (ffmpeg prints 30000/1001 as `29.97` and 24000/1001 as `23.98`); any other non-integer rate is limited to a denominator of 1001.
- **Checked.** Clips made here at 24, 25, 23.976, 29.97, 60 and 12.5 fps read back as 24/1, 25/1, 24000/1001, 30000/1001, 60/1 and 25/2. `tests/test_tools_resolver.py`, `test_probe_colours.py` and `test_ffmpeg_source_fallback.py`: 35 passed, 1 skipped. ruff clean.

## 2.15.4 · a paired device does not get the terminal

- **The hole.** `remote.Marked` marks every request from the network listener with `formcut.remote`, and `LocalOnly` admits a paired device to every route there. `app/terminal.py` never looked at the mark, so a paired phone, or anyone on the LAN who read its cookie from the plain-HTTP traffic on port 8977, could open `/api/terminal/ws` and get a login shell as the desktop user.
- **The fix.** The terminal socket closes with 1008 before `accept` when the scope carries `formcut.remote`, and `/api/terminal/status` answers 403 there, the way `remote._desktop` already guards device management. Loopback use is unchanged.
- **Checked.** A throwaway script outside the repo mounted the router behind a marker like `Marked`: the socket closed with 1008 and status answered 403; without the marker status answered 200. ruff clean.

## 2.15.4 · reversed copies and proxies are made without libx264

- **What broke.** `media.build_reversed` encoded its half-second pieces with `libx264`, and `proxies.build_proxy` encoded every proxy with it. The shipped ffmpeg is the LGPL build, which has no libx264, so in the desktop app Reverse failed at "Could not segment the source" (and an export holding a reversed clip failed with it), and every proxy build failed.
- **The fix.** The reversed pieces use `mpeg4 -q:v 2`, the encoder the LGPL bundle check itself encodes with, and the concat step and `.mp4` names are unchanged. A proxy keeps its libx264 settings when `encoders.detect()` found a working libx264 (a source checkout with a full ffmpeg), and otherwise is all-intra `mpeg4 -q:v 3`; the sidecar records which encoder made it.
- **Checked.** A throwaway script outside the repo with this machine's ffmpeg: a 2 s 24 fps clip with audio reversed into mpeg4 video and AAC audio, and a proxy built with libx264 hidden from `detect` came out mpeg4 at 24/1 with `"encoder": "mpeg4"` in its sidecar. Not run against the LGPL bundle itself. ruff clean.

## 2.15.4 · the Google Drive and TikTok sign-in callbacks get through LocalOnly

- **What broke.** The provider sends the browser back to `http://127.0.0.1:<port>/api/cloud/google/callback` or `/api/connect/tiktok/callback/` through a cross-site redirect, so the navigation carries no Origin and `Sec-Fetch-Site: cross-site`. `LocalOnly` refuses exactly that, so both sign-ins ended on "Local API request refused" and no account was stored. The tests passed because TestClient sends no Fetch Metadata.
- **The fix.** A loopback `GET` to one of those two exact paths is let through when it is a top-level navigation: `Sec-Fetch-Mode` is `navigate` and `Sec-Fetch-Dest` is `document`, or the headers are absent (a browser without Fetch Metadata). Frames, images and fetches to the same paths are still refused. Each handler still pops its one-time `state` first and answers 400 for an unknown or expired one, so a forged navigation changes nothing.
- **Checked.** A throwaway script outside the repo mounted both routers behind `LocalOnly`: a cross-site navigation to either callback with an unknown state answers 400 (was 403), the same request as an iframe or image load answers 403, and `/api/cloud` stays 403. `tests/test_family_guard.py`: 47 passed; `tests/test_cloud.py` and `tests/test_tiktok.py` pass. ruff clean.

## 2.15.4 · an audio package's chain is one comma list, nothing more

- **The hole.** `_check_chain` in `app/effect_packages.py` split a chain on `,` and checked only the first filter name of each piece, but ffmpeg's filtergraph syntax also has `;` chains and `[label]` pads. `volume=1[a];[a]ametadata=mode=print:file=<path>` passed as `volume` and, rendered through `-af`, created or truncated the named file; `amovie=` in the same position mixed in any local audio file.
- **The fix.** A chain holding `;`, `[`, `]`, a quote or a backslash is refused ("a chain is one list of filters separated by commas") before the per-filter check, so the allowlist sees every filter that will run. None of the allowlisted filters takes a file argument.
- **Checked.** A throwaway script outside the repo: both report payloads are refused, `volume={gain},highpass=f=200` still loads. `tests/test_effect_library.py` with a cv2 stub plugin from outside the repo: 11 passed, 1 failed (`test_every_look_renders_and_no_two_are_the_same`, which needs the real OpenCV that is not installed here). ruff clean.

## 2.15.4 · the system file dialogs take no script text from an extension

- **The hole.** `linking.choose` writes the dialog as AppleScript (macOS) or PowerShell (Windows) source. An extension's `files.open` `accept` list reached the AppleScript `of type {...}` list between plain double quotes, and its `files.save` name reached a single-quoted PowerShell string unescaped, so an extension could close the string and run a command as the person, outside its sandboxed frame. A trailing backslash in a title or name could also end an AppleScript string early.
- **The fix.** On macOS, types are kept only when they are 1 to 16 ASCII letters or digits, and the title and default name lose backslashes as well as double quotes. On Windows, the default name drops double quotes and doubles every character PowerShell reads as a single quote (`'` and U+2018 to U+201B). `/api/extensions/open` refuses an `accept` entry that is not such an extension with 422.
- **Checked.** A throwaway script outside the repo replaced `subprocess.run` and `platform.system` and printed the script text for the report's payloads: the injected macOS type is dropped, the save name stays inside its string, and the PowerShell name stays one quoted literal. Not run on macOS or Windows. ruff clean.

## 2.15.4 · a template's media asset is staged under a fresh name

- **The hole.** `restore` in `app/template_assets.py` named the staged file for a `mediaId` asset from the template's own asset key and `suffix`, both untrusted. A key such as `x/../../folder/notes` made `mkdir` create `template-x` and the `..` steps resolve past it, so `write_bytes` overwrote a file outside the data folder and the `finally` unlink then deleted it.
- **The fix.** The staged name is `template-<uuid hex><suffix>`, and the suffix (lower-cased, `.bin` when absent) must match `\.[a-z0-9]{1,8}` or the import is refused with `ValueError`, which `import_template` already answers as 422.
- **Checked.** A throwaway script outside the repo (cv2 stubbed, `ingest_path` replaced): a template whose key climbs to a sibling folder left that folder's file untouched and staged `template-<hex>.txt` in the data folder; suffixes `/../x.txt` and `.t/x` were refused. ruff clean.

## 2.15.3 · malformed package entries are refused, not crashed on

- **What happened.** `import_package` turns `ValueError`, `KeyError` and `TypeError` into a 422, but a package whose `assets.json` or `media/index.json` held a non-object value hit `.get` on an int or string and raised `AttributeError`, a 500.
- **The fix.** `_restore_assets` refuses a non-object asset ("Invalid package assets") and the media loop in `unpack` refuses a non-object index entry ("Malformed package"), the messages the module already uses.

## 2.15.3 · expressions fail as ValueError

- **What escaped.** `evaluate` in `app/expressions.py` promised `ValueError` for an expression it cannot use. Division or modulo by zero, a float too large for `floor` or `ceil`, a function called with the wrong number of arguments, and text that does not parse (`2+`, `((((`) raised `ZeroDivisionError`, `OverflowError`, `TypeError` or `SyntaxError` instead. The call sites in `brush.py` (line 34) and `project_tracking.py` (line 71) have no `try` of their own; the enclosing route handlers catch `ValueError` (`brush.py` `source_brush`, `project_tracking.py` the track route) and answer 422, so only a `ValueError` was handled there and the other exceptions became a 500. `renderer.transform_at` has no handler, so a `ValueError` from it propagates to whoever renders the frame.
- **The fix.** The parse and the walk are wrapped: `SyntaxError`, `RecursionError` and `MemoryError` from `ast.parse` become `ValueError("Expression could not be parsed")`, and `ArithmeticError` and `TypeError` from the walk become `ValueError("Expression could not be evaluated")`. Results already handled (non-finite, over 1e6) are unchanged.

## 2.15.3 · a project file's media entries are checked as well as their ids

- **Found in review.** The id guard left three siblings in `open_file` and `_keep_record` (`app/project_files.py`). A media entry that is not an object (`"<32hex>": 5`) raised `AttributeError` at `entry.get`; a `path` or `relative` that is not text raised `TypeError` in `Path()`; and `_keep_record` spread the entry's own keys after `"id"`, so an entry holding `"id": "../../x"` replaced the validated id in the library index.
- **The fix.** The loop skips entries that are not objects, `path` and `relative` are candidates only when they are text, and the spread leaves out `"id"` as well as `"relative"`. Checked outside the repo with cv2 stubbed: an entry `{"id": "../../x", ...}` under a valid key is stored under the key, and a non-object entry or a numeric path is skipped without an error.

## 2.15.3 · a project file's media ids are checked before they name a file

- **The hole.** `open_file` in `app/project_files.py` took the keys of an .fmc's media table as media ids and passed them to `media.media_path` and `linking.link_path`. `linking._place` globs `MEDIA_DIR/<id>.*`, unlinks what it finds there and plants a symlink at `MEDIA_DIR/<id><ext>`, so an id such as `../../folder/*` deleted files outside the data folder and wrote a link there. Reproduced outside the repo with the cv2 import stubbed: two files in a sibling folder were deleted.
- **The fix.** The media loop skips any id that does not fully match `media._ID` (32 hex digits, the id every library item gets), before the library lookup, the link, the missing list or `_keep_record` see it. The other callers are safe as they are: `link_files` passes no id, and `relink` goes through `media._find`, which only knows indexed ids.
- **Checked.** The same repro with the guard: the folder keeps both files and nothing is linked.

## 2.14.0 · extension host (Form Extension Contract, API 1)

- **Kit vendored unchanged.** `app/formext_host.py` is the contract kit's resolver and file checks, byte for byte, so every Form app refuses the same manifests with the same words. It is excluded from ruff in `ruff.toml` because formatting it would make it differ from the kit; `app/extensions.py` wraps it.
- **Routes from the features tuple.** `app/extensions.py` is one more entry in `features.py`, as the invariant says. The list is cached against `kit.stamp` (the two files' modification times), so the 2 s poll from the window costs two `stat` calls; `?reload=true` re-resolves regardless, which is how a development extension's edited manifest is picked up without touching `dev.json`.
- **Origin exemption, narrow.** `LocalOnly` refuses any request whose Origin is not the window's and any cross-site request with no Origin. A sandboxed frame has an opaque origin, so its module scripts arrive with `Origin: null` and its stylesheet and image loads with no Origin and `Sec-Fetch-Site: cross-site`. `GET` and `HEAD` under `/api/extensions/files/` from loopback are let through with any Origin and any `Sec-Fetch-Site`, as the contract's 07:47 wording says (the integration pass widened the first cut, which allowed only absent or `null` Origins and GET, and added HEAD to the route, which had answered it with the SPA's 404). The prefix serves only a package's own files and changes nothing; every other route still refuses `Origin: null` and web origins (403). The files are the package's own, served with `Access-Control-Allow-Origin: *` as the contract asks.
- **404 with headers.** A refused file answers 404 with no body but still carries nosniff, no-store, CORP and ACAO. `LocalOnly` adds its own nosniff too, so that header appears twice; harmless, left rather than special-casing the middleware.
- **Dialogs and save stay in one request.** `/api/extensions/save` opens the system save dialog and writes in the same request, so the path always comes from the person's own choice; there is no "write bytes to this path" route an extension page could reach. `/api/extensions/open` reads only what the dialog returned, filtered by `accept`, 200 MB in total.
- **Fetch only to the public internet.** formcut already reaches the network (stock, registry, cloud), so `net.fetch` is offered, through the engine because the frame's CSP has `connect-src 'none'`. https only, no redirects followed (the extension sees the 3xx and decides), cookies and formcut's own headers stripped, and every resolved address must be global: loopback, private, link-local and multicast are refused. A DNS answer could still change between the check and the connect; accepted for a permission the person granted by name.
- **The window bridge.** There was no route from the MCP server to the window, and extension pages, their consent and their storage live in the window. `ask_window` queues a request; the window long-polls `GET /api/extensions/agent/next` (25 s) and posts the answer to `/api/extensions/agent/{id}`. A request nobody claims in 15 s means no window is open, and says so (6 s was too short on a loaded machine, where the window's next poll took longer to arrive). `extensions.list` then falls back to the engine's own view without permission state.
- **RPC in the thread pool for these two.** `http_rpc` is async and calls the synchronous dispatcher on the loop thread. `extensions.command` waits for the window, and the window answers through the same loop, so waiting there deadlocked until the timeout. Only methods starting `extensions.` are moved to `run_in_threadpool`; every other method keeps running as before. The `/api/rpc/ws` websocket does the same (integration pass: it ran them on the loop and would have stalled the whole engine for up to 150 s). `app.cli`'s framings run in their own process, where no window ever polls.
- **Fail at once with no window.** The contract asks a CLI that cannot reach a window to fail at once. `agent_next` records when a window last polled; `ask_window` refuses straight away when none has in 35 s (one 25 s long-poll plus slack), so `app.cli` and an engine with its window closed answer "the formcut window is not open" immediately instead of after the 15 s claim wait.
- **Prefixed tool names.** The MCP tools are `formcut_extensions_list` and `formcut_extension_command`: every formcut tool carries the `formcut_` prefix, and the contract (07:47 resolution) names them `<prefix>_extensions_list` and `<prefix>_extension_command` on such servers. The README count is 34. `_rpc` gained a `timeout` argument so the command tool can wait 180 s (the window allows 150 s for a command plus the consent dialog).
- **Save without a dialog.** `/api/extensions/save` with `downloads: true` writes into `~/Downloads` (created when missing) as `name (2).ext` when the name is taken, the contract's fallback for a host with no save dialog. Only the base name is used, leading dots stripped, so the window's confirm dialog cannot aim it elsewhere. The window sends it only after the person confirms the name in formcut's own dialog.
